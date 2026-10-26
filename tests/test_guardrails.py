import json

import pytest

from slothcast.agent.guardrails import check_no_invented_numbers, validate_plan_dict
from slothcast.agent.planner import build_plan, template_plan
from slothcast.agent.prompts import PlanContext

CTX = PlanContext("DSA block", 120, 3, 3, "Elevated")


def good(**over):
    d = {"first_step": "Open the problem and sketch an approach.", "first_step_minutes": 15,
         "fallback": "Do one short session tonight.", "fallback_minutes": 10,
         "note": "A small start beats none."}
    d.update(over)
    return d


@pytest.mark.parametrize("text", ["There is a 72% chance you skip", "about 0.72 likely", "7 in 10 days slip", "80 percent risk"])
def test_invented_numbers_are_rejected(text):
    assert not check_no_invented_numbers(text, 0.5)[0]


def test_percentage_matching_the_model_is_allowed():
    assert check_no_invented_numbers("Risk is 50% today", 0.5)[0]


def test_minutes_are_fine():
    assert check_no_invented_numbers("Work for 15 minutes", None)[0]


def test_validate_rejects_bad_minutes_and_missing_keys():
    assert not validate_plan_dict(good(first_step_minutes=500), 120, 0.5)[0]
    assert not validate_plan_dict(good(first_step_minutes=2), 120, 0.5)[0]
    bad = good(); bad.pop("note")
    assert not validate_plan_dict(bad, 120, 0.5)[0]
    assert validate_plan_dict(good(), 120, 0.5)[0]


def test_planner_uses_valid_llm_output():
    plan = build_plan(CTX, 0.5, llm_call=lambda p, s: json.dumps(good()))
    assert plan.source.startswith("llm:") and plan.first_step_minutes == 15


def test_planner_falls_back_on_invented_probability():
    plan = build_plan(CTX, 0.5, llm_call=lambda p, s: json.dumps(good(note="You have a 90% chance of skipping")))
    assert plan.source == "template" and "rejected" in plan.guardrail_note


def test_planner_falls_back_on_garbage_and_errors():
    assert build_plan(CTX, 0.5, llm_call=lambda p, s: "not json").source == "template"

    def boom(p, s):
        raise ConnectionError("no ollama")

    plan = build_plan(CTX, 0.5, llm_call=boom)
    assert plan.source == "template" and "unavailable" in plan.guardrail_note


def test_template_plan_shrinks_with_risk():
    low = template_plan(PlanContext("x", 120, 3, 3, "Low"))
    high = template_plan(PlanContext("x", 120, 3, 3, "High"))
    assert high.first_step_minutes < low.first_step_minutes
    assert template_plan(PlanContext("x", 8, 3, 3, "High")).first_step_minutes >= 5
