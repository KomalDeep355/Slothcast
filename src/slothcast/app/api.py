from __future__ import annotations

import logging
import os
from datetime import date as Date, datetime
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from slothcast import config
from slothcast.coach import HabitCoachError, generate_habit_coaching
from slothcast.demo_data import write_demo
from slothcast.habits import build_habit_forecast
from slothcast.ingest.checkin import append_checkin, set_outcome
from slothcast.pipeline import forecast_tomorrow, load_dataset

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="Slothcast API",
    description="Personal deadline-risk forecasting and practical next-step planning.",
    version="0.2.0",
)

default_origins = (
    "http://localhost:5500,"
    "http://127.0.0.1:5500,"
    "http://localhost:8000,"
    "http://127.0.0.1:8000"
)

allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "SLOTHCAST_CORS_ORIGINS", default_origins
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class ForecastRequest(BaseModel):
    task: str = Field(min_length=1, max_length=200)
    planned_minutes: int = Field(default=60, ge=10, le=600)
    days_to_deadline: int = Field(default=3, ge=0, le=60)
    energy: int | None = Field(default=3, ge=1, le=5)
    date: Date | None = None
    model: Literal["auto", "logistic", "random_forest", "tabpfn"] = "auto"
    use_tabpfn: bool = False
    use_llm: bool = False
    use_demo: bool = False


class CheckinRequest(BaseModel):
    date: Date | None = None
    task: str = Field(min_length=1, max_length=200)
    planned_minutes: int = Field(ge=10, le=600)
    days_to_deadline: int = Field(ge=0, le=60)
    energy: int | None = Field(default=3, ge=1, le=5)
    completed_0_1: Literal[0, 1] | None = None


class OutcomeRequest(BaseModel):
    date: Date | None = None
    completed: Literal[0, 1]


def _json_records(frame: pd.DataFrame) -> list[dict]:
    records = frame.to_dict(orient="records")
    cleaned = []

    for record in records:
        item = {}

        for key, value in record.items():
            if value is None or value is pd.NA or value is pd.NaT:
                item[key] = None
                continue

            if isinstance(value, (pd.Timestamp, datetime, Date)):
                item[key] = value.isoformat()
                continue

            try:
                missing = pd.isna(value)
                if isinstance(missing, bool) and missing:
                    item[key] = None
                    continue
            except (TypeError, ValueError):
                pass

            if hasattr(value, "item"):
                value = value.item()

            item[key] = value

        cleaned.append(item)

    return cleaned


def _checkins_path(use_demo: bool = False) -> Path:
    if not use_demo:
        return Path(config.CHECKINS_PATH)

    demo_path = Path(config.SAMPLE_CHECKINS_PATH)

    if not demo_path.exists():
        write_demo(demo_path)

    return demo_path


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error(
        "%s (%s)",
        message,
        type(exc).__name__,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return HTTPException(
        status_code=500,
        detail=message,
    )


@app.get("/", include_in_schema=False)
def root():
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=500,
            detail="Frontend index.html was not found.",
        )
    return FileResponse(index_file)


@app.get("/style.css", include_in_schema=False)
def frontend_styles():
    return FileResponse(FRONTEND_DIR / "style.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def frontend_script():
    return FileResponse(
        FRONTEND_DIR / "app.js",
        media_type="application/javascript",
    )


@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "slothcast-api",
        "version": app.version,
    }


@app.get("/api/status")
def status():
    try:
        dataset = load_dataset(
            config.CHECKINS_PATH,
            config.COMMITS_PATH,
        )

        return {
            "status": "ok",
            "project": "Slothcast",
            "sufficiency": dataset.sufficiency.to_dict(),
            "labelled_days": len(dataset.labeled),
            "synthetic_demo_available": True,
            "default_model": "logistic",
            "llm_enabled_by_default": False,
        }

    except Exception as exc:
        raise _internal_error(
            "Could not load Slothcast data.",
            exc,
        ) from exc


@app.post("/api/forecast")
def forecast(request: ForecastRequest):
    task = request.task.strip()

    if not task:
        raise HTTPException(
            status_code=422,
            detail="Task cannot be blank.",
        )

    try:
        checkins_path = _checkins_path(request.use_demo)

        result = forecast_tomorrow(
            task=task,
            planned_minutes=request.planned_minutes,
            days_to_deadline=request.days_to_deadline,
            energy=request.energy,
            date=request.date.isoformat() if request.date else None,
            checkins_path=checkins_path,
            commits_path=config.COMMITS_PATH,
            use_llm=request.use_llm,
            model=request.model,
            use_tabpfn=request.use_tabpfn,
        )

        response = result.to_dict()
        response["data_mode"] = (
            "synthetic_demo"
            if request.use_demo
            else "personal_history"
        )

        return response

    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise _internal_error(
            "Forecast failed. Check the server logs for details.",
            exc,
        ) from exc


@app.post("/api/checkins")
def create_checkin(request: CheckinRequest):
    task = request.task.strip()

    if not task:
        raise HTTPException(
            status_code=422,
            detail="Task cannot be blank.",
        )

    try:
        frame = append_checkin(
            config.CHECKINS_PATH,
            date=request.date,
            planned_task=task,
            planned_minutes=request.planned_minutes,
            days_to_deadline=request.days_to_deadline,
            energy=request.energy,
            completed=request.completed_0_1,
            label_source="verified",
        )

        return {
            "ok": True,
            "message": "Check-in saved.",
            "saved_rows": len(frame),
        }

    except (ValueError, OSError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise _internal_error(
            "Could not save the check-in.",
            exc,
        ) from exc


@app.post("/api/outcome")
def record_outcome(request: OutcomeRequest):
    try:
        frame = set_outcome(
            config.CHECKINS_PATH,
            request.date,
            request.completed,
            label_source="verified",
        )

        return {
            "ok": True,
            "message": "Outcome saved.",
            "labelled_rows": int(
                frame["completed_0_1"].notna().sum()
            ),
        }

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (ValueError, OSError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise _internal_error(
            "Could not save the task outcome.",
            exc,
        ) from exc


@app.get("/api/history")
def history(
    limit: int = Query(default=30, ge=1, le=365),
):
    try:
        dataset = load_dataset(
            config.CHECKINS_PATH,
            config.COMMITS_PATH,
        )

        rows = (
            dataset.labeled
            .sort_values("date", ascending=False)
            .head(limit)
        )

        return {
            "sufficiency": dataset.sufficiency.to_dict(),
            "count": len(dataset.labeled),
            "items": _json_records(rows),
        }

    except Exception as exc:
        raise _internal_error(
            "Could not load task history.",
            exc,
        ) from exc


@app.get("/api/habits/forecast")
def habit_forecast():
    return build_habit_forecast(config.CHECKINS_PATH)


@app.get("/api/habits/coach")
def habit_coach():
    forecast = build_habit_forecast(config.CHECKINS_PATH)
    try:
        return generate_habit_coaching(forecast)
    except HabitCoachError as exc:
        logger.error("Could not generate habit coaching: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="The configured habit coaching provider could not complete the request.",
        ) from exc


app.mount(
    "/",
    StaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend",
)
