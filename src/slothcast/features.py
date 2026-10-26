"""Leakage-free features: row i only ever sees outcomes of rows < i."""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = [
    "weekday",
    "is_weekend",
    "planned_minutes",
    "days_to_deadline",
    "deadline_pressure",
    "energy",
    "prev_slip",
    "slip_rate_7",
    "slip_streak",
    "commits_prev_day",
]


def history_stats(past: list[int]) -> dict:
    """Stats from earlier labelled days (not calendar-adjacent days: the last N logged rows)."""
    last7 = past[-7:]
    streak = 0
    for v in reversed(past):
        if v == 1:
            streak += 1
        else:
            break
    return {
        "prev_slip": float(past[-1]) if past else np.nan,
        "slip_rate_7": float(np.mean(last7)) if last7 else np.nan,
        "slip_streak": float(streak),
    }


def row_features(date, planned_minutes, days_to_deadline, energy, past: list[int], commits_prev_day: float = 0.0) -> dict:
    date = pd.Timestamp(date)
    dtd = float(np.clip(days_to_deadline, 0, 30))
    out = {
        "weekday": float(date.weekday()),
        "is_weekend": float(date.weekday() >= 5),
        "planned_minutes": float(planned_minutes),
        "days_to_deadline": dtd,
        "deadline_pressure": 1.0 / (1.0 + dtd),
        "energy": float(energy) if energy is not None and not pd.isna(energy) else np.nan,
        "commits_prev_day": float(commits_prev_day),
    }
    out.update(history_stats(past))
    return out


def commits_lookup(commits: pd.DataFrame | None) -> dict:
    if commits is None or len(commits) == 0:
        return {}
    c = commits.copy()
    c["date"] = pd.to_datetime(c["date"]).dt.normalize()
    return c.groupby("date")["commits"].sum().astype(float).to_dict()


def build_features(labeled: pd.DataFrame, commits: pd.DataFrame | None = None) -> pd.DataFrame:
    lookup = commits_lookup(commits)
    outcomes = labeled["y_slip"].astype(int).tolist()
    rows = []
    for i, (_, r) in enumerate(labeled.iterrows()):
        prev_commits = lookup.get(r["date"] - pd.Timedelta(days=1), 0.0)
        rows.append(
            row_features(r["date"], r["planned_minutes"], r["days_to_deadline"], r["energy"], outcomes[:i], prev_commits)
        )
    return pd.DataFrame(rows, columns=FEATURES, index=labeled.index)


def next_row_features(
    labeled: pd.DataFrame,
    date,
    planned_minutes: float,
    days_to_deadline: float,
    energy: float | None = None,
    commits: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Features for a future day, using the whole labelled history."""
    lookup = commits_lookup(commits)
    day = pd.Timestamp(date).normalize()
    prev_commits = lookup.get(day - pd.Timedelta(days=1), 0.0)
    past = labeled["y_slip"].astype(int).tolist()
    return pd.DataFrame([row_features(day, planned_minutes, days_to_deadline, energy, past, prev_commits)], columns=FEATURES)
