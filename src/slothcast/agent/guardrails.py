"""The LLM may phrase a plan. It may never produce a probability.

Numbers come from the statistical model only. Anything that looks like a probability in LLM
output is rejected and the deterministic template plan is used instead.
"""
from __future__ import annotations

import re

PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", re.I)
DECIMAL_PROB = re.compile(r"(?<![\d.])0?\.\d+(?!\d)")
ODDS = re.compile(r"\b\d+\s*(?:in|out of)\s*\d+\b", re.I)


def check_no_invented_numbers(text: str, risk_p: float | None) -> tuple[bool, str]:
    allowed = {round(risk_p * 100)} if risk_p is not None else set()
    for m in PERCENT.finditer(text):
        if round(float(m.group(1))) not in allowed:
            return False, f"unexpected percentage '{m.group(0)}'"
    if DECIMAL_PROB.search(text):
        return False, "probability-like decimal"
    if ODDS.search(text):
        return False, "odds-style number"
    return True, "ok"


def validate_plan_dict(data: object, planned_minutes: float, risk_p: float | None) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "not a JSON object"
    for key in ("first_step", "fallback", "note"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            return False, f"missing text field '{key}'"
        if len(data[key]) > 300:
            return False, f"'{key}' too long"
    for key in ("first_step_minutes", "fallback_minutes"):
        v = data.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return False, f"'{key}' must be a number"
        if not (5 <= v <= max(5, planned_minutes)):
            return False, f"'{key}' outside 5..{int(planned_minutes)}"
    for key in ("first_step", "fallback", "note"):
        ok, why = check_no_invented_numbers(data[key], risk_p)
        if not ok:
            return False, f"{key}: {why}"
    return True, "ok"
