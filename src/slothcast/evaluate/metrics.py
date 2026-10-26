from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

EDGES = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0000001])


def brier(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def log_loss_(y, p, eps: float = 1e-6) -> float:
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def accuracy(y, p, thr: float = 0.5) -> float:
    return float(np.mean((np.asarray(p) >= thr).astype(int) == np.asarray(y)))


def auc(y, p) -> float:
    y = np.asarray(y)
    return float("nan") if len(np.unique(y)) < 2 else float(roc_auc_score(y, p))


def reliability_table(y, p) -> pd.DataFrame:
    y, p = np.asarray(y, float), np.asarray(p, float)
    idx = np.digitize(p, EDGES) - 1
    rows = []
    for b in range(len(EDGES) - 1):
        m = idx == b
        if m.any():
            rows.append({"bin": f"{EDGES[b]:.1f}-{min(EDGES[b+1], 1.0):.1f}", "n": int(m.sum()),
                         "mean_pred": float(p[m].mean()), "frac_slip": float(y[m].mean())})
    return pd.DataFrame(rows, columns=["bin", "n", "mean_pred", "frac_slip"])


def ece(y, p) -> float:
    t = reliability_table(y, p)
    if t.empty:
        return float("nan")
    return float((t["n"] * (t["mean_pred"] - t["frac_slip"]).abs()).sum() / t["n"].sum())


def summarize(y, p) -> dict:
    return {"n": int(len(y)), "brier": brier(y, p), "log_loss": log_loss_(y, p),
            "accuracy": accuracy(y, p), "auc": auc(y, p), "ece": ece(y, p)}


def bootstrap_brier_gain(y, p_model, p_base, n_boot: int = 2000, seed: int = 0) -> dict:
    """Brier(base) - Brier(model) with a 90% bootstrap interval over test rows.

    Rows are resampled independently, which ignores serial correlation: treat the interval as
    optimistic. A gain > 0 means the model beats the base rate.
    """
    y, pm, pb = (np.asarray(a, float) for a in (y, p_model, p_base))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(y), size=(n_boot, len(y)))
    gains = ((pb[idx] - y[idx]) ** 2 - (pm[idx] - y[idx]) ** 2).mean(axis=1)
    lo, hi = np.percentile(gains, [5, 95])
    return {"mean": float(np.mean((pb - y) ** 2 - (pm - y) ** 2)), "ci90": [float(lo), float(hi)]}
