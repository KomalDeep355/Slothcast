from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from slothcast.agent.guardrails import check_no_invented_numbers


class HabitCoachError(RuntimeError):
    """Raised when a configured coaching provider cannot return a valid response."""


def _safe_context(forecast: dict[str, Any]) -> dict[str, Any]:
    summary = forecast.get("summary") or {}
    patterns = forecast.get("patterns") or {}

    return {
        "summary": {
            "labelled_tasks": summary.get("labelled_tasks"),
            "completed_tasks": summary.get("completed_tasks"),
            "postponed_tasks": summary.get("postponed_tasks"),
            "overall_completion_rate_pct": summary.get(
                "overall_completion_rate_pct"
            ),
            "change_vs_previous_period_percentage_points": summary.get(
                "change_vs_previous_period_percentage_points"
            ),
        },
        "patterns": {
            key: [
                {
                    "group": item.get("group"),
                    "observations": item.get("observations"),
                    "completion_rate_pct": item.get("completion_rate_pct"),
                }
                for item in (patterns.get(key) or [])
            ]
            for key in (
                "by_weekday",
                "by_energy",
                "by_planned_duration",
                "by_deadline_proximity",
            )
        },
        "insights": [
            {
                "title": item.get("title"),
                "detail": item.get("detail"),
            }
            for item in (forecast.get("insights") or [])
        ],
    }


def generate_habit_coaching(forecast: dict[str, Any]) -> dict[str, Any]:
    base_url = os.getenv("SLOTHCAST_LLM_BASE_URL", "").rstrip("/")
    api_key = os.getenv("SLOTHCAST_LLM_API_KEY", "")
    model = os.getenv("SLOTHCAST_LLM_MODEL", "")

    if not (base_url and api_key and model):
        return {
            "available": False,
            "message": (
                "Llama coaching is not configured. Your numerical habit forecast "
                "is still available."
            ),
        }

    try:
        parsed_url = urlsplit(base_url)
        hostname = parsed_url.hostname
    except ValueError as exc:
        raise HabitCoachError("Configured provider URL is invalid.") from exc

    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed_url.scheme != "https" and not (
        parsed_url.scheme == "http" and hostname in local_hosts
    ):
        raise HabitCoachError(
            "Use HTTPS for hosted providers; HTTP is allowed only for localhost."
        )

    request_body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a supportive habit coach. Explain the supplied "
                    "aggregated task statistics and offer one manageable next "
                    "step. Describe patterns qualitatively; do not state "
                    "percentages, probabilities, odds, diagnoses, or claims "
                    "that you were trained on the user's history. "
                    "When the data is sparse or null, say that personal patterns "
                    "are not established yet. Be concise, kind, and practical."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(_safe_context(forecast)),
            },
        ],
        "temperature": 0.3,
        "max_tokens": 250,
    }
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            provider_response = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HabitCoachError(
            f"Provider returned HTTP status {exc.code}."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise HabitCoachError("Could not reach the configured provider.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HabitCoachError("Provider returned invalid JSON.") from exc

    try:
        coaching = provider_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HabitCoachError("Provider response did not contain coaching text.") from exc

    if not isinstance(coaching, str) or not coaching.strip():
        raise HabitCoachError("Provider returned empty coaching text.")

    numbers_valid, reason = check_no_invented_numbers(coaching, None)
    if not numbers_valid:
        raise HabitCoachError(f"Provider returned unsupported numeric claims: {reason}.")

    return {
        "available": True,
        "coaching": coaching.strip(),
    }
