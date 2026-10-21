"""Nightly check-in log: the single source of ground truth.

One row per day. `completed_0_1` may be blank (plan logged, outcome not yet known).
`label_source` says how trustworthy the outcome is:
  verified  - you recorded it yourself
  inferred  - derived (e.g. from commits)
  synthetic - generated demo data, never mix with real results
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .. import config

COLUMNS = [
    "date",
    "planned_task",
    "planned_minutes",
    "days_to_deadline",
    "energy_1_5",
    "completed_0_1",
    "label_source",
]
VALID_SOURCES = {"verified", "inferred", "synthetic"}


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for col in ["planned_minutes", "days_to_deadline", "energy_1_5", "completed_0_1"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    src = df["label_source"].fillna("verified").astype(str).str.strip().str.lower()
    df["label_source"] = src.where(src != "", "verified")
    df["planned_task"] = df["planned_task"].fillna("").astype(str)
    return df


def _validate(df: pd.DataFrame) -> None:
    bad = set(df["label_source"]) - VALID_SOURCES
    if bad:
        raise ValueError(f"label_source must be one of {sorted(VALID_SOURCES)}, got {sorted(bad)}")
    if df["date"].isna().any():
        raise ValueError("date is required")
    if (df["planned_minutes"].isna() | (df["planned_minutes"] <= 0)).any():
        raise ValueError("planned_minutes must be a positive number")
    if (df["days_to_deadline"].isna() | (df["days_to_deadline"] < 0)).any():
        raise ValueError("days_to_deadline must be a number >= 0")
    energy = df["energy_1_5"].dropna()
    if ((energy < 1) | (energy > 5)).any():
        raise ValueError("energy_1_5 must be between 1 and 5 (or blank)")
    done = df["completed_0_1"].dropna()
    if (~done.isin([0, 1])).any():
        raise ValueError("completed_0_1 must be 0, 1 or blank")


def _save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.sort_values("date").copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out[COLUMNS].to_csv(path, index=False)


def load_checkins(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path or config.CHECKINS_PATH)
    if not path.exists():
        return _coerce(pd.DataFrame(columns=COLUMNS))
    raw = pd.read_csv(path)
    missing = [c for c in COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")
    df = _coerce(raw[COLUMNS])
    _validate(df)
    return df.sort_values("date").reset_index(drop=True)


def append_checkin(
    path: str | Path | None = None,
    *,
    date,
    planned_task: str,
    planned_minutes: float,
    days_to_deadline: float,
    energy: float | None = None,
    completed: int | None = None,
    label_source: str = "verified",
) -> pd.DataFrame:
    """Add (or replace) the row for `date`."""
    path = Path(path or config.CHECKINS_PATH)
    df = load_checkins(path)
    day = pd.Timestamp(date).normalize()
    row = _coerce(
        pd.DataFrame(
            [
                {
                    "date": day,
                    "planned_task": planned_task,
                    "planned_minutes": planned_minutes,
                    "days_to_deadline": days_to_deadline,
                    "energy_1_5": energy,
                    "completed_0_1": completed,
                    "label_source": label_source,
                }
            ]
        )
    )
    _validate(row)
    frames = [f for f in (df[df["date"] != day], row) if not f.empty]
    out = pd.concat(frames, ignore_index=True)
    _save(out, path)
    return out


def set_outcome(path: str | Path | None, date, completed: int, label_source: str = "verified") -> pd.DataFrame:
    """Record whether the planned work for `date` happened."""
    path = Path(path or config.CHECKINS_PATH)
    df = load_checkins(path)
    day = pd.Timestamp(date).normalize()
    mask = df["date"] == day
    if not mask.any():
        raise KeyError(f"no check-in for {day.date()}; log the plan first")
    df.loc[mask, "completed_0_1"] = completed
    df.loc[mask, "label_source"] = label_source
    _validate(df)
    _save(df, path)
    return df
