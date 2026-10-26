from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from slothcast import config  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src" / "slothcast" / "app" / "main.py"


def _patch(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CHECKINS_PATH", tmp_path / "raw" / "checkins.csv")
    monkeypatch.setattr(config, "COMMITS_PATH", tmp_path / "raw" / "commits.csv")
    monkeypatch.setattr(config, "SAMPLE_CHECKINS_PATH", tmp_path / "sample" / "demo_log.csv")
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "results")


def test_dashboard_renders_with_synthetic_warning(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    assert not at.exception
    assert any("synthetic" in w.value.lower() for w in at.warning)


def test_dashboard_forecast_button_shows_metrics_and_plan(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens -> template plan
    monkeypatch.setattr(config, "OLLAMA_URL", "http://127.0.0.1:9")
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    at.sidebar.selectbox[0].set_value("logistic")
    at.run()
    at.button[0].click().run()
    assert not at.exception
    assert [m.label for m in at.metric] == ["Deadline risk", "Slip probability", "Model"]
