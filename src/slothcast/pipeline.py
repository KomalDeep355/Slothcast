"""High-level operations shared by the CLI, dashboard and Temporal workflow."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config
from .agent.planner import Plan, build_plan
from .agent.prompts import PlanContext
from .evaluate.report import run_report
from .features import build_features, next_row_features
from .ingest.checkin import load_checkins
from .ingest.github import load_commits
from .labels import build_labels
from .models.baselines import make_model
from .models.common import risk_label
from .models.tabpfn_model import tabpfn_status
from .observability import span
from .sufficiency import Sufficiency, assess


@dataclass
class Dataset:
    labeled: pd.DataFrame
    commits: pd.DataFrame | None
    dropped: int
    sufficiency: Sufficiency


@dataclass
class Forecast:
    date: str
    risk: float | None  # P(slip); None when history is insufficient
    label: str
    model_used: str | None
    model_note: str
    sufficiency: Sufficiency
    plan: Plan

    def to_dict(self) -> dict:
        return {"date": self.date, "risk": self.risk, "label": self.label, "model_used": self.model_used,
                "model_note": self.model_note, "sufficiency": self.sufficiency.to_dict(), "plan": self.plan.to_dict()}


def load_dataset(checkins_path=None, commits_path=None) -> Dataset:
    checkins = load_checkins(checkins_path)
    commits = load_commits(commits_path)
    labeled, dropped = build_labels(checkins, commits)
    return Dataset(labeled, commits, dropped, assess(labeled))


def forecast_tomorrow(
    task: str,
    planned_minutes: float,
    days_to_deadline: float,
    energy: float | None = None,
    date=None,
    checkins_path=None,
    commits_path=None,
    use_llm: bool = True,
    model: str = "auto",
    use_tabpfn: bool = True,
    llm_call=None,
) -> Forecast:
    with span("forecast", model_pref=model, use_llm=use_llm):
        ds = load_dataset(checkins_path, commits_path)
        target = pd.Timestamp(date).normalize() if date is not None else pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
        risk, used, note = None, None, ""

        if ds.sufficiency.level == "insufficient":
            note = ds.sufficiency.message
        else:
            X = build_features(ds.labeled, ds.commits)
            y = ds.labeled["y_slip"].to_numpy()
            x_new = next_row_features(ds.labeled, target, planned_minutes, days_to_deadline, energy, ds.commits)
            order = ["tabpfn", "logistic"] if (model == "auto" and use_tabpfn) else ["logistic"] if model == "auto" else [model]
            for name in order:
                if name == "tabpfn":
                    ok, why = tabpfn_status()
                    if not ok:
                        note += f"tabpfn skipped: {why}. "
                        continue
                try:
                    with span("forecast.fit", model=name, n_rows=len(y)):
                        m = make_model(name).fit(X, y)
                        risk = float(m.predict_proba(x_new)[0])
                    used = name
                    break
                except Exception as exc:
                    note += f"{name} failed ({type(exc).__name__}: {exc}). "
            if used is None and not note:
                note = "no model could be fitted"

        label = risk_label(risk)
        ctx = PlanContext(task, planned_minutes, days_to_deadline, energy, label)
        plan = build_plan(ctx, risk, use_llm=use_llm, llm_call=llm_call)
        shown = "Not enough history yet" if risk is None else label
        return Forecast(str(target.date()), risk, shown, used, note.strip(), ds.sufficiency, plan)


def run_eval(checkins_path=None, commits_path=None, out_dir=None, use_tabpfn: bool = True,
             min_train: int = config.MIN_TRAIN, step: int = 1, only=None) -> dict:
    ds = load_dataset(checkins_path, commits_path)
    return run_report(ds.labeled, ds.commits, out_dir, use_tabpfn, min_train, step, only)


def save_plan(plan_input: dict, path=None) -> Path:
    path = Path(path or config.PLAN_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan_input, indent=2))
    return path


def load_plan(path=None) -> dict:
    path = Path(path or config.PLAN_PATH)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; create it with `slothcast set-plan`")
    return json.loads(path.read_text())


def write_outbox(result: dict, outbox_dir=None) -> Path:
    outbox = Path(outbox_dir or config.OUTBOX_DIR)
    outbox.mkdir(parents=True, exist_ok=True)
    p = result["plan"]
    risk = "not enough history yet" if result["risk"] is None else f"{result['label']} ({round(result['risk'] * 100)}% slip probability)"
    text = (f"# Slothcast forecast for {result['date']}\n\n**Deadline risk:** {risk}\n\n"
            f"**Data:** {result['sufficiency']['message']}\n\n"
            f"**Start with:** {p['first_step']}\n\n**If it slips:** {p['fallback']}\n\n{p['note']}\n\n"
            f"_model: {result['model_used']} | plan: {p['source']}_\n")
    path = outbox / f"{result['date']}.md"
    path.write_text(text)
    return path


def run_nightly(plan_path=None, checkins_path=None, commits_path=None, use_llm: bool = True,
                use_tabpfn: bool = True, outbox_dir=None) -> Path:
    plan = load_plan(plan_path)
    fc = forecast_tomorrow(
        plan["task"], plan["minutes"], plan["deadline_days"], plan.get("energy"),
        checkins_path=checkins_path, commits_path=commits_path, use_llm=use_llm, use_tabpfn=use_tabpfn,
    )
    return write_outbox(fc.to_dict(), outbox_dir)
