from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any

from app.models import Dataset, Interview
from app.scheduler.policy import TIER_WEIGHTS
from app.scheduler.validator import validate_schedule
from app.time_utils import day_of


def _scheduled(interviews: list[Interview]) -> list[Interview]:
    return [i for i in interviews if i.status in {"scheduled", "completed"} and i.scheduled_start is not None and i.scheduled_end is not None]


def schedule_metrics(dataset: Dataset, previous: list[Interview] | None = None) -> dict[str, Any]:
    requested = [i for i in dataset.interviews if i.status != "cancelled"]
    scheduled = _scheduled(dataset.interviews)
    total_weight = sum(TIER_WEIGHTS.get(i.priority, 1) for i in requested) or 1
    scheduled_weight = sum(TIER_WEIGHTS.get(i.priority, 1) for i in scheduled)
    validation = validate_schedule(dataset)

    room_minutes = Counter()
    room_capacity = Counter()
    panel_minutes = Counter()
    panel_capacity = Counter()
    for room in dataset.rooms:
        room_capacity[room.id] = sum(9 * 60 for _ in range(4))
    for panel in dataset.panels:
        panel_capacity[panel.id] += max(0, panel.available_until - panel.available_from)
    for interview in scheduled:
        if interview.room_id:
            room_minutes[interview.room_id] += interview.duration
        if interview.panel_id:
            panel_minutes[interview.panel_id] += interview.duration

    waits: list[int] = []
    by_student_day: dict[tuple[str, int], list[Interview]] = defaultdict(list)
    for interview in scheduled:
        by_student_day[(interview.student_id, day_of(interview.scheduled_start or 0))].append(interview)
    for items in by_student_day.values():
        items.sort(key=lambda i: i.scheduled_start or 0)
        for left, right in zip(items, items[1:]):
            waits.append(max(0, (right.scheduled_start or 0) - (left.scheduled_end or 0)))

    previous_by_id = {i.id: i for i in previous or []}
    changed_existing = 0
    future_existing = 0
    shifts: list[int] = []
    for interview in scheduled:
        old = previous_by_id.get(interview.id)
        if old and old.scheduled_start is not None:
            future_existing += 1
            changed = (
                old.scheduled_start != interview.scheduled_start
                or old.room_id != interview.room_id
                or old.panel_id != interview.panel_id
                or old.status != interview.status
            )
            if changed:
                changed_existing += 1
                shifts.append(abs((interview.scheduled_start or 0) - old.scheduled_start))
    churn = changed_existing / future_existing if future_existing else 0.0
    unscheduled_reasons = Counter(i.unscheduled_reason_code or "UNKNOWN" for i in dataset.interviews if i.status == "unscheduled")
    return {
        "requested_interviews": len(requested),
        "scheduled_interviews": len(scheduled),
        "unscheduled_interviews": sum(1 for i in dataset.interviews if i.status == "unscheduled"),
        "coverage": round(len(scheduled) / len(requested), 4) if requested else 1,
        "weighted_coverage": round(scheduled_weight / total_weight, 4),
        "student_conflicts": sum(1 for v in validation["violations"] if v["code"] == "STUDENT_ID_OVERLAP"),
        "room_conflicts": sum(1 for v in validation["violations"] if v["code"] == "ROOM_ID_OVERLAP"),
        "panel_conflicts": sum(1 for v in validation["violations"] if v["code"] == "PANEL_ID_OVERLAP"),
        "validation": validation,
        "room_utilisation": {rid: round(room_minutes[rid] / cap, 4) if cap else 0 for rid, cap in room_capacity.items()},
        "overall_room_utilisation": round(sum(room_minutes.values()) / (sum(room_capacity.values()) or 1), 4),
        "panel_utilisation": {pid: round(panel_minutes[pid] / cap, 4) if cap else 0 for pid, cap in panel_capacity.items()},
        "average_student_wait_minutes": round(mean(waits), 2) if waits else 0,
        "median_student_wait_minutes": round(median(waits), 2) if waits else 0,
        "p95_student_wait_minutes": sorted(waits)[int(len(waits) * 0.95) - 1] if waits else 0,
        "unscheduled_by_reason": dict(unscheduled_reasons),
        "replan_churn": round(churn, 4),
        "schedule_stability": round(1 - churn, 4),
        "total_shifted_minutes": sum(shifts),
        "average_shifted_minutes": round(mean(shifts), 2) if shifts else 0,
        "maximum_shifted_minutes": max(shifts) if shifts else 0,
    }

