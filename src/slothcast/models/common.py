"""Shared helpers for all models. Every model predicts P(slip) = P(planned work does not happen)."""
from __future__ import annotations

import numpy as np

from .. import config


def smoothed_rate(y) -> float:
    y = np.asarray(y)
    return float((y.sum() + 1) / (len(y) + 2))  # Laplace smoothing


def p_slip_from_proba(model, proba: np.ndarray) -> np.ndarray:
    """Pick the column of predict_proba that corresponds to class 1."""
    classes = list(getattr(model, "classes_", [0, 1]))
    return np.asarray(proba)[:, classes.index(1)]


def risk_label(p: float | None) -> str:
    if p is None:
        return "Unknown"
    if p < config.RISK_LOW_MAX:
        return "Low"
    if p < config.RISK_ELEVATED_MAX:
        return "Elevated"
    return "High"
