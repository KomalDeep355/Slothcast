import json
from io import BytesIO
from urllib.request import Request

import pytest

from slothcast import coach


def test_coach_is_unavailable_without_configuration(monkeypatch):
    for name in (
        "SLOTHCAST_LLM_BASE_URL",
        "SLOTHCAST_LLM_API_KEY",
        "SLOTHCAST_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    result = coach.generate_habit_coaching({"summary": {"labelled_tasks": 3}})

    assert result["available"] is False
    assert "numerical habit forecast" in result["message"]


def test_coach_sends_aggregates_without_task_names(monkeypatch):
    monkeypatch.setenv("SLOTHCAST_LLM_BASE_URL", "https://coach.example/v1")
    monkeypatch.setenv("SLOTHCAST_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SLOTHCAST_LLM_MODEL", "llama-test")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return BytesIO(
            json.dumps(
                {"choices": [{"message": {"content": "Try one small next step."}}]}
            ).encode("utf-8")
        )

    monkeypatch.setattr(coach, "urlopen", fake_urlopen)
    result = coach.generate_habit_coaching(
        {
            "summary": {
                "labelled_tasks": 4,
                "completed_tasks": 3,
                "overall_completion_rate_pct": 75.0,
            },
            "patterns": {
                "by_weekday": [
                    {
                        "group": "Monday",
                        "observations": 2,
                        "completion_rate_pct": 50.0,
                    }
                ]
            },
            "insights": [{"title": "Early pattern", "detail": "Still forming."}],
            "recent_postponed_tasks": [{"task": "secret task name"}],
        }
    )

    request = captured["request"]
    assert isinstance(request, Request)
    assert request.full_url == "https://coach.example/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert captured["timeout"] == 30
    body = json.loads(request.data)
    user_context = body["messages"][1]["content"]
    assert "secret task name" not in user_context
    assert "recent_postponed_tasks" not in user_context
    assert "75.0" in user_context
    assert result == {"available": True, "coaching": "Try one small next step."}


def test_coach_rejects_insecure_remote_provider(monkeypatch):
    monkeypatch.setenv("SLOTHCAST_LLM_BASE_URL", "http://coach.example/v1")
    monkeypatch.setenv("SLOTHCAST_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SLOTHCAST_LLM_MODEL", "llama-test")

    with pytest.raises(coach.HabitCoachError, match="Use HTTPS"):
        coach.generate_habit_coaching({})


def test_coach_reports_provider_failures(monkeypatch):
    monkeypatch.setenv("SLOTHCAST_LLM_BASE_URL", "https://coach.example/v1")
    monkeypatch.setenv("SLOTHCAST_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SLOTHCAST_LLM_MODEL", "llama-test")

    def fake_urlopen(request, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(coach, "urlopen", fake_urlopen)

    with pytest.raises(coach.HabitCoachError, match="Could not reach"):
        coach.generate_habit_coaching({})


def test_coach_rejects_percentage_claims(monkeypatch):
    monkeypatch.setenv("SLOTHCAST_LLM_BASE_URL", "https://coach.example/v1")
    monkeypatch.setenv("SLOTHCAST_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SLOTHCAST_LLM_MODEL", "llama-test")
    monkeypatch.setattr(
        coach,
        "urlopen",
        lambda request, timeout: BytesIO(
            json.dumps(
                {"choices": [{"message": {"content": "There is a 90% chance."}}]}
            ).encode("utf-8")
        ),
    )

    with pytest.raises(coach.HabitCoachError, match="unsupported numeric claims"):
        coach.generate_habit_coaching({})
