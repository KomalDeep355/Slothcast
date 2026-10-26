"""Command line interface:  python -m slothcast.cli <command>  (or `slothcast <command>`)."""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

from . import config
from .demo_data import write_demo
from .ingest import backfill, checkin
from .ingest.github import update_commits_csv
from .observability import init_sentry
from .pipeline import forecast_tomorrow, run_eval, run_nightly, save_plan


def _today() -> str:
    return str(pd.Timestamp.today().normalize().date())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="slothcast", description="Deadline-risk forecaster (local-first).")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("log", help="log a day's plan (and optionally its outcome)")
    s.add_argument("--date", default=_today())
    s.add_argument("--task", required=True)
    s.add_argument("--minutes", type=float, required=True)
    s.add_argument("--deadline-days", type=float, required=True)
    s.add_argument("--energy", type=float)
    s.add_argument("--done", type=int, choices=[0, 1], help="1 = the work happened, 0 = it slipped")
    s.add_argument("--checkins", default=None)

    s = sub.add_parser("done", help="record the outcome for a logged day")
    s.add_argument("--date", default=_today())
    s.add_argument("--done", type=int, choices=[0, 1], required=True)
    s.add_argument("--checkins", default=None)

    s = sub.add_parser("ingest-github", help="pull commit counts into data/raw/github_commits.csv")
    s.add_argument("--user", default=os.environ.get("GITHUB_USER"))
    s.add_argument("--since", default=None, help="YYYY-MM-DD (default: 120 days ago)")

    s = sub.add_parser("import-csv", help="backfill past records from a CSV")
    s.add_argument("path")
    s.add_argument("--source", default="inferred", choices=["verified", "inferred"])

    s = sub.add_parser("demo-data", help="write a synthetic demo log (tagged synthetic)")
    s.add_argument("--days", type=int, default=90)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--out", default=None)

    s = sub.add_parser("eval", help="chronological evaluation -> results/")
    s.add_argument("--checkins", default=None)
    s.add_argument("--commits", default=None)
    s.add_argument("--out", default=None)
    s.add_argument("--min-train", type=int, default=config.MIN_TRAIN)
    s.add_argument("--step", type=int, default=1)
    s.add_argument("--no-tabpfn", action="store_true")

    s = sub.add_parser("forecast", help="forecast + plan for tomorrow")
    s.add_argument("--task", required=True)
    s.add_argument("--minutes", type=float, required=True)
    s.add_argument("--deadline-days", type=float, required=True)
    s.add_argument("--energy", type=float)
    s.add_argument("--date", default=None)
    s.add_argument("--checkins", default=None)
    s.add_argument("--model", default="auto", choices=["auto", "tabpfn", "logistic", "random_forest"])
    s.add_argument("--no-llm", action="store_true")
    s.add_argument("--no-tabpfn", action="store_true")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("set-plan", help="save tomorrow's plan for the nightly run")
    s.add_argument("--task", required=True)
    s.add_argument("--minutes", type=float, required=True)
    s.add_argument("--deadline-days", type=float, required=True)
    s.add_argument("--energy", type=float)

    s = sub.add_parser("nightly", help="ingest (optional) + forecast + write data/outbox/<date>.md")
    s.add_argument("--github-user", default=os.environ.get("GITHUB_USER"))
    s.add_argument("--no-llm", action="store_true")
    s.add_argument("--no-tabpfn", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    init_sentry()
    a = build_parser().parse_args(argv)

    if a.cmd == "log":
        checkin.append_checkin(a.checkins, date=a.date, planned_task=a.task, planned_minutes=a.minutes,
                               days_to_deadline=a.deadline_days, energy=a.energy, completed=a.done)
        print(f"logged {a.date}")
    elif a.cmd == "done":
        checkin.set_outcome(a.checkins, a.date, a.done)
        print(f"recorded outcome for {a.date}")
    elif a.cmd == "ingest-github":
        if not a.user:
            sys.exit("--user or GITHUB_USER required")
        out = update_commits_csv(a.user, os.environ.get("GITHUB_TOKEN"), a.since)
        print(f"{len(out)} days with commits saved to {config.COMMITS_PATH}")
    elif a.cmd == "import-csv":
        n = backfill.import_csv(a.path, default_source=a.source)
        print(f"imported {n} new rows (existing dates untouched)")
    elif a.cmd == "demo-data":
        out = a.out or config.SAMPLE_CHECKINS_PATH
        write_demo(out, a.days, a.seed)
        print(f"wrote synthetic demo log to {out}")
    elif a.cmd == "eval":
        res = run_eval(a.checkins, a.commits, a.out, not a.no_tabpfn, a.min_train, a.step)
        if "error" in res:
            print(res["error"])
        else:
            print(f"{res['sufficiency']['message']}\n")
            print(f"{'model':<15}{'n':>5}{'Brier':>9}{'skill':>9}{'AUC':>8}")
            for name, m in sorted(res["models"].items(), key=lambda kv: kv[1]["brier"]):
                skill = m.get("brier_skill_vs_base")
                auc = m["auc"]
                print(f"{name:<15}{m['n']:>5}{m['brier']:>9.3f}{('' if skill is None else f'{skill:.3f}'):>9}"
                      f"{('n/a' if auc != auc else f'{auc:.3f}'):>8}")
            for k, v in res["skipped_or_failed"].items():
                print(f"  skipped {k}: {v}")
            print(f"\nwrote {a.out or config.RESULTS_DIR}/results.md")
    elif a.cmd == "forecast":
        fc = forecast_tomorrow(a.task, a.minutes, a.deadline_days, a.energy, a.date, a.checkins,
                               use_llm=not a.no_llm, model=a.model, use_tabpfn=not a.no_tabpfn)
        if a.json:
            print(json.dumps(fc.to_dict(), indent=2, default=str))
        else:
            risk = "—" if fc.risk is None else f"{round(fc.risk * 100)}% slip probability"
            print(f"Forecast for {fc.date}: {fc.label} ({risk})")
            print(f"Data: {fc.sufficiency.message}")
            if fc.model_note:
                print(f"Note: {fc.model_note}")
            print(f"Model: {fc.model_used or 'none'}\n")
            print(f"Start with ({fc.plan.first_step_minutes} min): {fc.plan.first_step}")
            print(f"If it slips ({fc.plan.fallback_minutes} min): {fc.plan.fallback}")
            print(f"{fc.plan.note}  [{fc.plan.source}]")
            if fc.plan.guardrail_note:
                print(f"({fc.plan.guardrail_note})")
    elif a.cmd == "set-plan":
        print(f"saved {save_plan({'task': a.task, 'minutes': a.minutes, 'deadline_days': a.deadline_days, 'energy': a.energy})}")
    elif a.cmd == "nightly":
        if a.github_user:
            update_commits_csv(a.github_user, os.environ.get("GITHUB_TOKEN"))
        print(f"wrote {run_nightly(use_llm=not a.no_llm, use_tabpfn=not a.no_tabpfn)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
