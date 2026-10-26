from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlanContext:
    task: str
    planned_minutes: float
    days_to_deadline: float
    energy: float | None
    risk_label: str  # Low | Elevated | High | Unknown


SYSTEM = """You help someone start planned work when it might slip. Be warm, practical and brief. No guilt, no lectures.
Hard rules:
- Never state, estimate or change any probability, percentage, odds or score. Use only the risk label you are given.
- The only numbers allowed in your text are minutes.
- Propose ONE small first step and ONE smaller fallback if the plan slips.
Reply with JSON only, exactly these keys:
{"first_step": str, "first_step_minutes": int, "fallback": str, "fallback_minutes": int, "note": str}
Minutes must be whole numbers between 5 and the planned minutes."""


def build_user_prompt(ctx: PlanContext) -> str:
    energy = "unknown" if ctx.energy is None else f"{ctx.energy:g} out of five"
    return (
        f"Planned task: {ctx.task}\n"
        f"Planned minutes: {ctx.planned_minutes:g}\n"
        f"Days to deadline: {ctx.days_to_deadline:g}\n"
        f"Energy: {energy}\n"
        f"Deadline risk label: {ctx.risk_label}\n"
        "Write the plan JSON."
    )
