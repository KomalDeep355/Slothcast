
from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean


def _parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date()
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_int(value: object) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None


def load_checkins(csv_path: str | Path) -> list[dict]:
    path = Path(csv_path)
    if not path.exists():
        return []

    records = []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            day = _parse_date(row.get("date", ""))
            completed = _parse_int(row.get("completed_0_1"))
            minutes = _parse_int(row.get("planned_minutes"))
            energy = _parse_int(row.get("energy_1_5"))
            deadline = _parse_int(row.get("days_to_deadline"))

            if day is None or completed not in (0, 1):
                continue

            records.append({
                "date": day,
                "task": (row.get("planned_task") or "Untitled task").strip(),
                "minutes": minutes,
                "energy": energy,
                "days_to_deadline": deadline,
                "completed": completed,
                "label_source": (row.get("label_source") or "").strip(),
            })

    return sorted(records, key=lambda item: item["date"])


def _rate(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return mean(row["completed"] for row in rows)


def _percentage(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value * 100, 1)


def _group_rate(rows: list[dict], key_function) -> list[dict]:
    groups = defaultdict(list)

    for row in rows:
        key = key_function(row)
        if key is not None:
            groups[key].append(row)

    result = []

    for key, items in groups.items():
        rate = _rate(items)
        result.append({
            "group": key,
            "observations": len(items),
            "completion_rate_pct": _percentage(rate),
        })

    return sorted(result, key=lambda item: str(item["group"]))


def build_habit_forecast(
    csv_path: str | Path,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    rows = load_checkins(csv_path)
    labelled = [row for row in rows if row["date"] <= today]

    last_7 = [
        row for row in labelled
        if today - timedelta(days=6) <= row["date"] <= today
    ]
    last_30 = [
        row for row in labelled
        if today - timedelta(days=29) <= row["date"] <= today
    ]
    previous_30 = [
        row for row in labelled
        if today - timedelta(days=59) <= row["date"] < today - timedelta(days=29)
    ]

    total = len(labelled)
    completed_total = sum(row["completed"] for row in labelled)
    postponed_total = total - completed_total

    overall_rate = _rate(labelled)
    recent_rate = _rate(last_7)
    monthly_rate = _rate(last_30)
    previous_rate = _rate(previous_30)

    daily_counts = defaultdict(int)
    for row in labelled:
        daily_counts[row["date"]] += 1

    observed_days = max(
        1,
        (max((row["date"] for row in labelled), default=today)
         - min((row["date"] for row in labelled), default=today)).days + 1,
    )

    tasks_per_day = total / observed_days if total else 0
    estimated_daily_tasks = round(tasks_per_day, 2)

    def project(days: int) -> dict:
        if overall_rate is None:
            return {
                "days": days,
                "expected_tasks": 0,
                "expected_completed": None,
                "expected_postponed": None,
                "message": "Record completed and postponed tasks to build this forecast.",
            }

        expected_tasks = round(estimated_daily_tasks * days, 1)
        expected_completed = round(expected_tasks * overall_rate, 1)
        expected_postponed = round(expected_tasks * (1 - overall_rate), 1)

        uncertainty = (
            "low"
            if total >= 30
            else "medium"
            if total >= 10
            else "high"
        )

        return {
            "days": days,
            "expected_tasks": expected_tasks,
            "expected_completed": expected_completed,
            "expected_postponed": expected_postponed,
            "expected_completion_rate_pct": _percentage(overall_rate),
            "uncertainty": uncertainty,
            "message": (
                "Historical-rate estimate, not a guarantee. "
                "It assumes your task volume and completion habits stay similar."
            ),
        }

    weekday_names = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]

    weekday_patterns = _group_rate(
        labelled,
        lambda row: weekday_names[row["date"].weekday()],
    )

    energy_patterns = _group_rate(
        labelled,
        lambda row: (
            f"Energy {row['energy']}/5"
            if row["energy"] is not None and 1 <= row["energy"] <= 5
            else None
        ),
    )

    duration_patterns = _group_rate(
        labelled,
        lambda row: (
            "Under 30 minutes" if row["minutes"] is not None and row["minutes"] < 30
            else "30–60 minutes" if row["minutes"] is not None and row["minutes"] <= 60
            else "Over 60 minutes" if row["minutes"] is not None
            else None
        ),
    )

    deadline_patterns = _group_rate(
        labelled,
        lambda row: (
            "Due today" if row["days_to_deadline"] == 0
            else "Due in 1–2 days" if row["days_to_deadline"] is not None and 1 <= row["days_to_deadline"] <= 2
            else "Due in 3–7 days" if row["days_to_deadline"] is not None and 3 <= row["days_to_deadline"] <= 7
            else "Due in over 7 days" if row["days_to_deadline"] is not None and row["days_to_deadline"] > 7
            else None
        ),
    )

    change_pp = None
    if recent_rate is not None and previous_rate is not None:
        change_pp = round((recent_rate - previous_rate) * 100, 1)

    insights = []

    if total < 5:
        insights.append({
            "type": "data",
            "title": "Your personal pattern is still forming",
            "detail": f"You have {total} labelled task outcomes. Add more verified check-ins before relying on habit predictions.",
        })
    elif total < 20:
        insights.append({
            "type": "data",
            "title": "Early personal signals",
            "detail": f"Your forecast uses {total} labelled outcomes. Treat patterns as provisional until more outcomes are recorded.",
        })
    else:
        insights.append({
            "type": "data",
            "title": "Personal history available",
            "detail": f"Your trends use {total} labelled task outcomes.",
        })

    if change_pp is not None:
        if change_pp >= 5:
            insights.append({
                "type": "positive",
                "title": "Completion is trending upward",
                "detail": f"Your recent 7-day completion rate is {change_pp} percentage points above the previous 30-day period.",
            })
        elif change_pp <= -5:
            insights.append({
                "type": "attention",
                "title": "Completion may be slipping",
                "detail": f"Your recent 7-day completion rate is {abs(change_pp)} percentage points below the previous 30-day period.",
            })
        else:
            insights.append({
                "type": "neutral",
                "title": "Completion looks broadly steady",
                "detail": "The recent and previous-period rates are relatively close.",
            })

    if not labelled:
        insights.append({
            "type": "data",
            "title": "Start with a real check-in",
            "detail": "Record whether a planned task was completed or postponed to unlock personal trends.",
        })

    return {
        "generated_on": today.isoformat(),
        "data_source": "recorded_checkins",
        "personalized": total >= 5,
        "summary": {
            "labelled_tasks": total,
            "completed_tasks": completed_total,
            "postponed_tasks": postponed_total,
            "overall_completion_rate_pct": _percentage(overall_rate),
            "last_7_days": {
                "labelled_tasks": len(last_7),
                "completion_rate_pct": _percentage(recent_rate),
            },
            "last_30_days": {
                "labelled_tasks": len(last_30),
                "completion_rate_pct": _percentage(monthly_rate),
            },
            "previous_30_days": {
                "labelled_tasks": len(previous_30),
                "completion_rate_pct": _percentage(previous_rate),
            },
            "change_vs_previous_period_percentage_points": change_pp,
        },
        "forecasts": {
            "next_7_days": project(7),
            "next_30_days": project(30),
        },
        "patterns": {
            "by_weekday": weekday_patterns,
            "by_energy": energy_patterns,
            "by_planned_duration": duration_patterns,
            "by_deadline_proximity": deadline_patterns,
        },
        "insights": insights,
        "recent_postponed_tasks": [
            {
                "date": row["date"].isoformat(),
                "task": row["task"],
                "planned_minutes": row["minutes"],
                "energy": row["energy"],
                "days_to_deadline": row["days_to_deadline"],
            }
            for row in reversed(labelled)
            if row["completed"] == 0
        ][:10],
        "limitations": [
            "These estimates use recorded outcomes, not a guarantee of future behaviour.",
            "A task-level risk score is separate from the overall habit forecast.",
            "The current CSV format is a single-user store. Add user authentication and isolated storage before offering multi-user accounts.",
        ],
    }
