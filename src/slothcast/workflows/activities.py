"""Temporal activities (sync, run in a thread pool). Each is idempotent and safe to retry."""
from __future__ import annotations

import os

from temporalio import activity

from .. import pipeline
from ..ingest.github import update_commits_csv


@activity.defn
def ingest_github(user: str) -> int:
    out = update_commits_csv(user, os.environ.get("GITHUB_TOKEN"))
    return int(len(out))


@activity.defn
def forecast(plan: dict) -> dict:
    fc = pipeline.forecast_tomorrow(
        plan["task"], plan["minutes"], plan["deadline_days"], plan.get("energy"),
        use_llm=plan.get("use_llm", True), use_tabpfn=plan.get("use_tabpfn", True),
    )
    return fc.to_dict()


@activity.defn
def write_outbox(result: dict) -> str:
    return str(pipeline.write_outbox(result))
