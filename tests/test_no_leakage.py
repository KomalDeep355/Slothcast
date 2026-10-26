import numpy as np
import pandas as pd

from slothcast.evaluate.report import collect_predictions
from slothcast.evaluate.splits import rolling_origin
from slothcast.features import build_features
from slothcast.models.baselines import build_registry


def test_features_use_only_past_outcomes(labeled):
    X1 = build_features(labeled)
    flipped = labeled.copy()
    flipped.loc[40:, "y_slip"] = 1 - flipped.loc[40:, "y_slip"]
    X2 = build_features(flipped)
    # row 40's features may depend on rows 0..39 only, so rows 0..40 must be identical
    pd.testing.assert_frame_equal(X1.iloc[:41], X2.iloc[:41])


def test_splits_are_chronological_and_cover_each_test_row_once():
    n, min_train = 50, 20
    seen = []
    for tr, te in rolling_origin(n, min_train, step=3):
        assert tr.max() < te.min()
        seen += list(te)
    assert seen == list(range(min_train, n))


def test_predictions_do_not_depend_on_future_labels(labeled):
    only = ["base_rate", "yesterday", "weekday", "logistic"]
    reg, _ = build_registry(use_tabpfn=False, only=only)
    n = len(labeled)
    cut = n - 10
    flipped = labeled.copy()
    flipped.loc[cut:, "y_slip"] = 1 - flipped.loc[cut:, "y_slip"]
    p1, _ = collect_predictions(labeled, build_features(labeled), reg, min_train=20)
    p2, _ = collect_predictions(flipped, build_features(flipped), reg, min_train=20)
    a = p1[p1["idx"] < cut].sort_values(["model", "idx"]).reset_index(drop=True)
    b = p2[p2["idx"] < cut].sort_values(["model", "idx"]).reset_index(drop=True)
    np.testing.assert_allclose(a["p_slip"].to_numpy(), b["p_slip"].to_numpy())
