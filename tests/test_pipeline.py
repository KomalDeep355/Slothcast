import json

import pandas as pd

from slothcast import pipeline
from slothcast.demo_data import write_demo


def test_eval_writes_all_artifacts_and_includes_base_rate(tmp_path):
    src = tmp_path / "demo.csv"
    write_demo(src, days=60, seed=1)
    out = tmp_path / "res"
    res = pipeline.run_eval(src, tmp_path / "none.csv", out, use_tabpfn=False, only=["base_rate", "yesterday", "logistic"])
    for f in ["metrics.json", "results.md", "calibration.png", "learning_curve.png", "predictions.csv"]:
        assert (out / f).exists(), f
    assert "base_rate" in res["models"] and "logistic" in res["models"]
    assert "synthetic" in (out / "results.md").read_text().lower()
    assert json.loads((out / "metrics.json").read_text())["n_rows"] == 60


def test_eval_reports_error_when_history_too_short(tmp_path):
    src = tmp_path / "demo.csv"
    write_demo(src, days=12, seed=1)
    res = pipeline.run_eval(src, tmp_path / "none.csv", tmp_path / "res", use_tabpfn=False)
    assert "error" in res


def test_forecast_refuses_probability_when_history_insufficient(tmp_path):
    src = tmp_path / "demo.csv"
    write_demo(src, days=8, seed=1)
    fc = pipeline.forecast_tomorrow("DSA", 90, 3, 3, checkins_path=src, commits_path=tmp_path / "x.csv", use_llm=False)
    assert fc.risk is None and fc.label == "Not enough history yet" and fc.model_used is None
    assert fc.plan.source == "template"


def test_forecast_returns_probability_with_enough_history(tmp_path):
    src = tmp_path / "demo.csv"
    write_demo(src, days=80, seed=2)
    fc = pipeline.forecast_tomorrow("DSA", 90, 3, 3, checkins_path=src, commits_path=tmp_path / "x.csv",
                                    use_llm=False, use_tabpfn=False, date="2026-10-22")
    assert 0 <= fc.risk <= 1 and fc.model_used == "logistic" and fc.date == "2026-10-22"


def test_nightly_writes_outbox(tmp_path):
    src = tmp_path / "demo.csv"
    write_demo(src, days=60, seed=2)
    plan = pipeline.save_plan({"task": "DSA", "minutes": 90, "deadline_days": 2, "energy": 3}, tmp_path / "plan.json")
    out = pipeline.run_nightly(plan, src, tmp_path / "x.csv", use_llm=False, use_tabpfn=False, outbox_dir=tmp_path / "box")
    assert out.exists() and "Slothcast forecast" in out.read_text()
