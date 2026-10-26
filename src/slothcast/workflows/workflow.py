"""Durable nightly run: ingest -> forecast -> write briefing. Survives crashes and retries flaky steps."""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import forecast, ingest_github, write_outbox

RETRY = RetryPolicy(initial_interval=timedelta(seconds=2), backoff_coefficient=2.0, maximum_attempts=5)


@workflow.defn
class NightlySlothcast:
    @workflow.run
    async def run(self, params: dict) -> str:
        if params.get("github_user"):
            try:  # commits are a nice-to-have: a GitHub outage must not block the forecast
                await workflow.execute_activity(
                    ingest_github, params["github_user"], start_to_close_timeout=timedelta(minutes=3), retry_policy=RETRY
                )
            except Exception as exc:  # noqa: BLE001
                workflow.logger.warning("github ingest failed after retries: %s", exc)
        result = await workflow.execute_activity(
            forecast, params["plan"], start_to_close_timeout=timedelta(minutes=5), retry_policy=RETRY
        )
        return await workflow.execute_activity(
            write_outbox, result, start_to_close_timeout=timedelta(minutes=1), retry_policy=RETRY
        )
