"""Synthetic demo log. ALWAYS tagged label_source=synthetic. Never report results from it as real."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ingest.checkin import COLUMNS

TASKS = ["DSA block", "Project work", "Write-up", "Reading"]


def make_demo_checkins(days: int = 90, seed: int = 7, end=None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = pd.Timestamp(end).normalize() if end is not None else pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    dates = pd.date_range(end=end, periods=days, freq="D")
    cycle_len = int(rng.integers(8, 14))
    dtd = cycle_len
    prev_slip = 0
    rows = []
    for d in dates:
        if dtd < 0:
            cycle_len = int(rng.integers(8, 14))
            dtd = cycle_len
        minutes = int(rng.choice([60, 90, 120, 150]))
        energy = int(np.clip(round(rng.normal(3, 1)), 1, 5))
        weekend = d.weekday() >= 5
        # hidden generative story: weekends, low energy, yesterday's slip and long blocks raise slip risk;
        # a far-away deadline raises it too, the last day before a deadline almost never slips
        logit = (
            -1.1
            + 0.9 * weekend
            - 0.5 * (energy - 3)
            + 0.8 * prev_slip
            + 0.004 * (minutes - 90)
            + 0.10 * min(dtd, 10)
            - 1.2 * (dtd <= 1)
        )
        slip = int(rng.random() < 1 / (1 + np.exp(-logit)))
        rows.append(
            {
                "date": d,
                "planned_task": TASKS[int(rng.integers(0, len(TASKS)))],
                "planned_minutes": minutes,
                "days_to_deadline": dtd,
                "energy_1_5": np.nan if rng.random() < 0.08 else energy,
                "completed_0_1": 1 - slip,
                "label_source": "synthetic",
            }
        )
        prev_slip = slip
        dtd -= 1
    df = pd.DataFrame(rows, columns=COLUMNS)
    return df


def write_demo(path, days: int = 90, seed: int = 7) -> pd.DataFrame:
    from pathlib import Path

    df = make_demo_checkins(days, seed)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)
    return df
