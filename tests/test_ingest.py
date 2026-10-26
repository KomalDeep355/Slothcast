import pandas as pd
import pytest

from slothcast.ingest import backfill, checkin
from slothcast.ingest.github import commits_to_daily


def test_commits_to_daily_buckets_by_local_day():
    commits = [
        {"commit": {"author": {"date": "2026-10-01T20:00:00Z"}}},  # 01:30 next day in IST
        {"commit": {"author": {"date": "2026-10-01T10:00:00Z"}}},
        {"commit": {"committer": {"date": "2026-10-03T10:00:00Z"}}},
    ]
    out = commits_to_daily(commits, tz="Asia/Kolkata")
    assert dict(zip(out["date"].dt.strftime("%Y-%m-%d"), out["commits"])) == {"2026-10-01": 1, "2026-10-02": 1, "2026-10-03": 1}
    assert commits_to_daily([]).empty


def test_checkin_roundtrip_and_outcome(tmp_path):
    p = tmp_path / "c.csv"
    checkin.append_checkin(p, date="2026-10-01", planned_task="DSA", planned_minutes=90, days_to_deadline=2, energy=4)
    df = checkin.load_checkins(p)
    assert len(df) == 1 and pd.isna(df["completed_0_1"].iloc[0])
    checkin.set_outcome(p, "2026-10-01", 0)
    assert checkin.load_checkins(p)["completed_0_1"].iloc[0] == 0
    checkin.append_checkin(p, date="2026-10-01", planned_task="DSA2", planned_minutes=60, days_to_deadline=1)  # replaces
    assert len(checkin.load_checkins(p)) == 1
    with pytest.raises(KeyError):
        checkin.set_outcome(p, "2026-12-01", 1)


@pytest.mark.parametrize("kw", [{"energy": 9}, {"planned_minutes": 0}, {"days_to_deadline": -1}, {"label_source": "guess"}])
def test_checkin_validation(tmp_path, kw):
    args = dict(date="2026-10-01", planned_task="x", planned_minutes=60, days_to_deadline=1)
    args.update(kw)
    with pytest.raises(ValueError):
        checkin.append_checkin(tmp_path / "c.csv", **args)


def test_backfill_defaults_to_inferred_and_never_overwrites(tmp_path):
    dest = tmp_path / "c.csv"
    checkin.append_checkin(dest, date="2026-10-02", planned_task="keep", planned_minutes=60, days_to_deadline=1, completed=1)
    src = tmp_path / "old.csv"
    pd.DataFrame({
        "date": ["2026-10-01", "2026-10-02"], "planned_task": ["a", "b"], "planned_minutes": [60, 60],
        "days_to_deadline": [2, 1], "energy_1_5": [3, 3], "completed_0_1": [0, 0],
    }).to_csv(src, index=False)
    assert backfill.import_csv(src, dest) == 1
    df = checkin.load_checkins(dest)
    assert df.loc[df["date"] == "2026-10-02", "planned_task"].iloc[0] == "keep"
    assert df.loc[df["date"] == "2026-10-01", "label_source"].iloc[0] == "inferred"
