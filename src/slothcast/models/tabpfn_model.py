"""TabPFN wrapper (TabPFN-3.5 via the `tabpfn` package, run LOCALLY by default).

Setup (once):
  1. pip install -e ".[tabpfn]"
  2. Accept the model license / sign in at https://platform.priorlabs.ai as Prior Labs describes
     (the open weights carry a non-commercial license: fine for research, evaluation, portfolio).
  3. First fit downloads the weights; after that it runs offline on CPU or GPU.

SLOTHCAST_TABPFN_MODE=client switches to Prior Labs' hosted API: your rows LEAVE your machine.
That is the opposite of the local-first story, so it is opt-in and flagged in the status text.
"""
from __future__ import annotations

import os

import numpy as np

from .. import config
from .common import p_slip_from_proba, smoothed_rate


def tabpfn_status() -> tuple[bool, str]:
    """(importable?, human-readable status). Weight/licence problems surface on first fit."""
    mode = config.TABPFN_MODE
    pkg = "tabpfn_client" if mode == "client" else "tabpfn"
    try:
        __import__(pkg)
    except Exception as exc:  # ImportError, or torch failing to load
        return False, f"{pkg} unavailable ({type(exc).__name__}); install with: pip install -e '.[tabpfn]'"
    if mode == "client":
        return True, "client mode: data is sent to Prior Labs' API"
    return True, "local mode: data stays on this machine"


class TabPFNSlip:
    name = "tabpfn"

    def __init__(self, mode: str | None = None):
        self.mode = mode or config.TABPFN_MODE

    def _make(self):
        if self.mode == "client":
            from tabpfn_client import TabPFNClassifier
        else:
            from tabpfn import TabPFNClassifier
        device = os.environ.get("SLOTHCAST_TABPFN_DEVICE")
        return TabPFNClassifier(device=device) if device and self.mode != "client" else TabPFNClassifier()

    def fit(self, X, y):
        y = np.asarray(y).astype(int)
        self.const = None
        if len(np.unique(y)) < 2:
            self.const = smoothed_rate(y)
            return self
        self.model = self._make()
        self.model.fit(X.to_numpy(dtype=float), y)  # TabPFN handles NaN itself
        return self

    def predict_proba(self, X) -> np.ndarray:
        if self.const is not None:
            return np.full(len(X), self.const)
        return p_slip_from_proba(self.model, self.model.predict_proba(X.to_numpy(dtype=float)))
