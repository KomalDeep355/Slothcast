import numpy as np

from slothcast.evaluate.metrics import bootstrap_brier_gain, brier, ece, reliability_table, summarize


def test_brier_perfect_and_worst():
    assert brier([1, 0], [1, 0]) == 0.0
    assert brier([1, 0], [0, 1]) == 1.0


def test_reliability_table_and_ece_perfectly_calibrated():
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 0])
    p = np.array([0.1] * 4 + [0.9] * 5 + [0.9])
    t = reliability_table(y, p)
    assert t["n"].sum() == 10
    assert ece(y, p) < 0.15


def test_auc_nan_when_single_class():
    assert np.isnan(summarize([1, 1, 1], [0.2, 0.5, 0.9])["auc"])


def test_bootstrap_gain_positive_for_better_model():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 200)
    good = np.where(y == 1, 0.8, 0.2)
    base = np.full(200, y.mean())
    g = bootstrap_brier_gain(y, good, base)
    assert g["mean"] > 0 and g["ci90"][0] > 0
