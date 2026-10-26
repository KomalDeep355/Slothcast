"""Chronological (rolling-origin) splits. Never shuffle time series."""
from __future__ import annotations

from typing import Iterator

import numpy as np


def rolling_origin(n: int, min_train: int = 20, step: int = 1) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Expanding window: train on rows [0, start), predict rows [start, start+step)."""
    for start in range(min_train, n, step):
        yield np.arange(0, start), np.arange(start, min(start + step, n))
