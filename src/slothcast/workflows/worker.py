"""Run the worker, start one run, or register a nightly schedule.

  temporal server start-dev                       # local dev server (separate terminal)
  python -m slothcast.workflows.worker            # worker
  python -m slothcast.workflows.worker --run-once # start one run and print the briefing path
  python -m slothcast.workflows.worker --schedule # run every day at 21:00 server time
"""
from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleSpec
from temporalio.worker import Worker

from ..pipeline import load_plan
from .activities import forecast, ingest_github, write_outbox
from .workflow import NightlySlothcast

TASK_QUEUE = "slothcast"


def _params() -> dict:
    return {"plan": load_plan(), "github_user": os.environ.get("GITHUB_USER")}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-once", action="store_true")
    ap.add_argument("--schedule", action="store_true")
    args = ap.parse_args()
    client = await Client.connect(os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"))

    if args.run_once:
        out = await client.execute_workflow(
            NightlySlothcast.run, _params(), id=f"slothcast-{uuid.uuid4().hex[:8]}", task_queue=TASK_QUEUE
        )
        print(out)
        return
    if args.schedule:
        await client.create_schedule(
            "slothcast-nightly",
            Schedule(
                action=ScheduleActionStartWorkflow(
                    NightlySlothcast.run, _params(), id="slothcast-nightly-run", task_queue=TASK_QUEUE
                ),
                spec=ScheduleSpec(cron_expressions=["0 21 * * *"]),
            ),
        )
        print("schedule created: daily at 21:00")
        return

    worker = Worker(
        client, task_queue=TASK_QUEUE, workflows=[NightlySlothcast],
        activities=[ingest_github, forecast, write_outbox], activity_executor=ThreadPoolExecutor(4),
    )
    print(f"worker listening on task queue '{TASK_QUEUE}'")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
