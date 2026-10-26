"""Forecast -> action. A local Gemma (via Ollama) phrases the plan; a deterministic template is the fallback."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Callable

import requests

from .. import config
from ..observability import span
from .guardrails import validate_plan_dict
from .prompts import SYSTEM, PlanContext, build_user_prompt


@dataclass
class Plan:
    first_step: str
    first_step_minutes: int
    fallback: str
    fallback_minutes: int
    note: str
    source: str  # "template" or "llm:<model>"
    guardrail_note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


_FIRST_MINUTES = {"Low": 25, "Elevated": 20, "High": 10, "Unknown": 15}
_NOTES = {
    "Low": "Looks like a normal day. Start as planned and reassess after the first block.",
    "Elevated": "This plan could slip. A smaller start keeps the day from turning into zero.",
    "High": "This plan is likely to slip, so the goal is a tiny start instead of the full block.",
    "Unknown": "There is not enough history for a forecast yet, so this is a gentle default.",
}


def template_plan(ctx: PlanContext) -> Plan:
    first = int(max(5, min(ctx.planned_minutes, _FIRST_MINUTES.get(ctx.risk_label, 15))))
    fallback = int(max(5, first // 2))
    if ctx.risk_label == "Low":
        step = f"Start '{ctx.task}' as planned. Work the first {first} minutes, then decide whether to continue."
    else:
        step = f"Open '{ctx.task}', write down the very first concrete action, and work on it for {first} minutes. Stopping after that is allowed."
    return Plan(
        first_step=step,
        first_step_minutes=first,
        fallback=f"If the plan slips, do one {fallback}-minute session of '{ctx.task}' before the day ends.",
        fallback_minutes=fallback,
        note=_NOTES.get(ctx.risk_label, _NOTES["Unknown"]),
        source="template",
    )


def default_llm_call(prompt: str, system: str) -> str:
    """POST to a local Ollama server. Raises on connection errors (caller falls back)."""
    with span("llm.generate", model=config.GEMMA_MODEL, prompt_chars=len(prompt)) as sp:
        resp = requests.post(
            f"{config.OLLAMA_URL}/api/generate",
            json={"model": config.GEMMA_MODEL, "system": system, "prompt": prompt, "stream": False,
                  "format": "json", "options": {"temperature": 0.4}},
            timeout=config.LLM_TIMEOUT_S,
        )
        resp.raise_for_status()
        body = resp.json()
        sp.set("prompt_tokens", body.get("prompt_eval_count"))
        sp.set("output_tokens", body.get("eval_count"))
        sp.set("response_chars", len(body.get("response", "")))
        return body.get("response", "")


def extract_json(text: str) -> object:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in LLM output")
    return json.loads(text[start : end + 1])


def build_plan(
    ctx: PlanContext,
    p_slip: float | None,
    use_llm: bool = True,
    llm_call: Callable[[str, str], str] | None = None,
) -> Plan:
    base = template_plan(ctx)
    if not use_llm:
        return base
    try:
        raw = (llm_call or default_llm_call)(build_user_prompt(ctx), SYSTEM)
        data = extract_json(raw)
    except Exception as exc:
        base.guardrail_note = f"LLM unavailable ({type(exc).__name__}); used the template plan."
        return base
    ok, why = validate_plan_dict(data, ctx.planned_minutes, p_slip)
    if not ok:
        base.guardrail_note = f"LLM output rejected ({why}); used the template plan."
        return base
    return Plan(
        first_step=data["first_step"].strip(),
        first_step_minutes=int(data["first_step_minutes"]),
        fallback=data["fallback"].strip(),
        fallback_minutes=int(data["fallback_minutes"]),
        note=data["note"].strip(),
        source=f"llm:{config.GEMMA_MODEL}",
    )
