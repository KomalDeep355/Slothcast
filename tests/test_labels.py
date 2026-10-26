import pandas as pd

from slothcast.ingest.checkin import COLUMNS, _coerce
from slothcast.labels import build_labels


def _rows(rows):
    return _coerce(pd.DataFrame(rows, columns=COLUMNS))


def test_recorded_outcomes_keep_their_source():
    df = _rows([
        ["2026-10-01", "a", 60, 3, 3, 1, "verified"],
        ["2026-10-02", "a", 60, 2, 2, 0, "verified"],
    ])
    lab, dropped = build_labels(df)
    assert dropped == 0
    assert lab["y_slip"].tolist() == [0, 1]
    assert set(lab["label_source"]) == {"verified"}


def test_blank_outcome_without_commit_data_is_dropped_not_guessed():
    df = _rows([["2026-10-01", "a", 60, 3, 3, None, "verified"]])
    lab, dropped = build_labels(df)
    assert lab.empty and dropped == 1


def test_blank_outcome_is_inferred_from_commits_only_inside_coverage():
    df = _rows([
        ["2026-10-01", "a", 60, 3, 3, None, "verified"],  # commits that day -> done
        ["2026-10-02", "a", 60, 3, 3, None, "verified"],  # inside coverage, zero commits -> slip
        ["2026-10-10", "a", 60, 3, 3, None, "verified"],  # outside coverage -> dropped
    ])
    commits = pd.DataFrame({"date": pd.to_datetime(["2026-10-01", "2026-10-03"]), "commits": [4, 1]})
    lab, dropped = build_labels(df, commits)
    assert dropped == 1
    assert lab["y_slip"].tolist() == [0, 1]
    assert set(lab["label_source"]) == {"inferred"}


def test_duplicate_dates_keep_last():
    df = _rows([
        ["2026-10-01", "a", 60, 3, 3, 1, "verified"],
        ["2026-10-01", "b", 60, 3, 3, 0, "verified"],
    ])
    lab, _ = build_labels(df)
    assert len(lab) == 1 and lab["y_slip"].iloc[0] == 1
