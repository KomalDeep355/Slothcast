"""Turn the raw log into honest labels.

Target `y_slip` = 1 when the planned work did NOT happen ("deadline risk" event).

Rules:
  * completed recorded            -> label, keeps its own label_source
  * completed blank + commit data covers that day -> inferred from commits (>= N commits = done)
  * otherwise                     -> dropped (unlabelled). Never guessed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_labels(
    checkins: pd.DataFrame,
    commits: pd.DataFrame | None = None,
    min_commits_for_done: int = 1,
) -> tuple[pd.DataFrame, int]:
    df = checkins.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)

    coverage = None
    counts: dict = {}
    if commits is not None and len(commits):
        c = commits.copy()
        c["date"] = pd.to_datetime(c["date"]).dt.normalize()
        counts = c.groupby("date")["commits"].sum().to_dict()
        coverage = (c["date"].min(), c["date"].max())

    y: list[float] = []
    src: list[str | None] = []
    for _, row in df.iterrows():
        done = row["completed_0_1"]
        if pd.notna(done):
            y.append(1 - int(done))
            src.append(row["label_source"])
        elif coverage is not None and coverage[0] <= row["date"] <= coverage[1]:
            y.append(0 if counts.get(row["date"], 0) >= min_commits_for_done else 1)
            src.append("inferred")
        else:
            y.append(np.nan)
            src.append(None)

    df["y_slip"] = y
    df["label_source"] = src
    n_dropped = int(df["y_slip"].isna().sum())
    labeled = df.dropna(subset=["y_slip"]).copy()
    labeled["y_slip"] = labeled["y_slip"].astype(int)
    labeled = labeled.rename(columns={"energy_1_5": "energy"}).drop(columns=["completed_0_1"])
    return labeled.reset_index(drop=True), n_dropped
