"""How does out-of-sample Brier change as the training history grows?"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import brier

BUCKETS = [(20, 29), (30, 44), (45, 59), (60, 89), (90, 10_000)]


def brier_by_train_size(preds: pd.DataFrame, min_n: int = 5) -> pd.DataFrame:
    rows = []
    for model, g in preds.groupby("model"):
        for lo, hi in BUCKETS:
            m = (g["n_train"] >= lo) & (g["n_train"] <= hi)
            if m.sum() >= min_n:
                label = f"{lo}-{hi}" if hi < 10_000 else f"{lo}+"
                rows.append({"model": model, "train_days": label, "n": int(m.sum()),
                             "brier": brier(g.loc[m, "y"], g.loc[m, "p_slip"])})
    return pd.DataFrame(rows, columns=["model", "train_days", "n", "brier"])
