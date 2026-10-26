"""Simple baselines. TabPFN has to beat these to earn its place; if it does not, say so."""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .common import p_slip_from_proba, smoothed_rate
from .tabpfn_model import TabPFNSlip, tabpfn_status


class BaseRate:
    name = "base_rate"

    def fit(self, X: pd.DataFrame, y):
        self.p = smoothed_rate(y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self.p)


class Yesterday:
    """P(slip | did yesterday's work slip?) with shrinkage towards the base rate."""

    name = "yesterday"

    def fit(self, X: pd.DataFrame, y):
        y = np.asarray(y)
        prev = X["prev_slip"].to_numpy()
        self.base = smoothed_rate(y)
        self.p = {}
        for v in (0.0, 1.0):
            m = prev == v
            self.p[v] = float((y[m].sum() + 2 * self.base) / (m.sum() + 2))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        prev = X["prev_slip"].to_numpy()
        return np.where(np.isnan(prev), self.base, np.where(prev == 1, self.p[1.0], self.p[0.0]))


class Weekday:
    """Smoothed slip rate per weekday."""

    name = "weekday"

    def fit(self, X: pd.DataFrame, y):
        y = np.asarray(y)
        wd = X["weekday"].to_numpy()
        self.base = smoothed_rate(y)
        self.p = {d: float((y[wd == d].sum() + 2 * self.base) / ((wd == d).sum() + 2)) for d in range(7)}
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.array([self.p.get(int(d), self.base) for d in X["weekday"].to_numpy()])


class SkModel:
    """sklearn pipeline wrapper that survives a single-class training set."""

    def __init__(self, name: str, make: Callable[[], object]):
        self.name = name
        self._make = make

    def fit(self, X: pd.DataFrame, y):
        y = np.asarray(y)
        self.const = None
        if len(np.unique(y)) < 2:
            self.const = smoothed_rate(y)
            return self
        self.model = self._make()
        self.model.fit(X, y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.const is not None:
            return np.full(len(X), self.const)
        return p_slip_from_proba(self.model, self.model.predict_proba(X))


def _logistic():
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(C=0.5, max_iter=1000)),
        ]
    )


def _forest():
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("clf", RandomForestClassifier(n_estimators=200, min_samples_leaf=3, random_state=0)),
        ]
    )


FACTORIES: dict[str, Callable[[], object]] = {
    "base_rate": BaseRate,
    "yesterday": Yesterday,
    "weekday": Weekday,
    "logistic": lambda: SkModel("logistic", _logistic),
    "random_forest": lambda: SkModel("random_forest", _forest),
    "tabpfn": TabPFNSlip,
}


def make_model(name: str):
    return FACTORIES[name]()


def build_registry(use_tabpfn: bool = True, only: list[str] | None = None) -> tuple[dict[str, Callable[[], object]], dict[str, str]]:
    """Return ({name: factory}, {name: reason it was skipped})."""
    notes: dict[str, str] = {}
    registry = {}
    for name, factory in FACTORIES.items():
        if only is not None and name not in only:
            continue
        if name == "tabpfn":
            if not use_tabpfn:
                notes[name] = "disabled (--no-tabpfn)"
                continue
            ok, why = tabpfn_status()
            if not ok:
                notes[name] = why
                continue
        registry[name] = factory
    return registry, notes
