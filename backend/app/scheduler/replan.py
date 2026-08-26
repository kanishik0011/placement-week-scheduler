from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from app.models import Dataset, EventLog, Interview
from app.scheduler.diagnostics import explain_unscheduled
from app.scheduler.engine import Occupancy, _can_assign, _rank_key, _search_slot
from app.scheduler.metrics import schedule_metrics
from app.scheduler.validator import validate_schedule
from app.time_utils import DEFAULT_FREEZE_MINUTES, hm, overlaps


def _same_assignment_possible(interview: Interview, dataset: Dataset, occ: Occupancy) -> Interview | None:
    if interview.scheduled_start is None or not interview.panel_id or not interview.room_id:
        return None
    students = {s.id: s for s in dataset.students}
    companies = {c.id: c for c in dataset.companies}
    panels = {p.id: p for p in dataset.panels}
    rooms = {r.id: r for r in dataset.rooms}
    student = students[interview.student_id]
    company = companies[interview.company_id]
    panel = panels.get(interview.panel_id)
    room = rooms.get(interview.room_id)
    if panel and room and _can_assign(interview, interview.scheduled_start, panel, room, student, company, occ):
        updated = replace(interview, status="scheduled")
        occ.add(updated)
        return updated
    return None


def classify_invalid(interview: Interview, dataset: Dataset, now: int, freeze_minutes: int) -> tuple[bool, str]:
    if interview.status not in {"scheduled", "unscheduled", "requested"}:
        return False, "completed_or_cancelled"
    students = {s.id: s for s in dataset.students}
    companies = {c.id: c for c in dataset.companies}
    panels = {p.id: p for p in dataset.panels}
    rooms = {r.id: r for r in dataset.rooms}
    student = students[interview.student_id]
    company = companies[interview.company_id]
    panel = panels.get(interview.panel_id or "")
    room = rooms.get(interview.room_id or "")
    if student.withdrawn:
        return True, "student withdrawn"
    if interview.status == "unscheduled":
        return False, "previously unresolved"
    if interview.scheduled_start is None or interview.scheduled_end is None:
        return True, "not assigned"
    if interview.scheduled_end <= now:
        return False, "completed"
    if panel is None or not panel.active:
        return True, "panel dropped"
    if room is None or not room.available:
        return True, "room unavailable"
    if interview.scheduled_start < company.available_start or interview.scheduled_end > company.available_end:
        return True, "company delay/window changed"
    for outage_start, outage_end in room.outage_windows:
        if overlaps(interview.scheduled_start, interview.scheduled_end, outage_start, outage_end):
            return True, "room outage"
    if interview.scheduled_start <= now + freeze_minutes:
        return False, "frozen near term"
    return False, "unaffected"


def _change_kind(old: Interview | None, new: Interview) -> str:
    if old is None:
        return "newly_scheduled"
    if new.status == "cancelled":
        return "cancelled"
    if new.status == "unscheduled" and old.status != "unscheduled":
        return "newly_unscheduled"
    if old.status == "unscheduled" and new.status == "scheduled":
        return "newly_scheduled"
    changed_time = old.scheduled_start != new.scheduled_start or old.scheduled_end != new.scheduled_end
    changed_room = old.room_id != new.room_id
    changed_panel = old.panel_id != new.panel_id
    if changed_time:
        return "moved"
    if changed_room:
        return "room_changed"
    if changed_panel:
        return "panel_changed"
    return "unchanged"


def replan_dataset(dataset: Dataset, now: int | None = None, freeze_minutes: int = DEFAULT_FREEZE_MINUTES) -> dict[str, Any]:
    started = time.perf_counter()
    now = dataset.current_time if now is None else now
    previous = [replace(i) for i in dataset.interviews]
    old_by_id = {i.id: i for i in previous}
    students = {s.id: s for s in dataset.students}
    companies = {c.id: c for c in dataset.companies}
    rooms = dataset.rooms
    panels = dataset.panels
    occ = Occupancy()
    kept: list[Interview] = []
    repair: list[tuple[Interview, str]] = []
    cancelled: list[Interview] = []

    for interview in previous:
        if students[interview.student_id].withdrawn and interview.status != "completed":
            if interview.scheduled_end is None or interview.scheduled_end > now:
                cancelled.append(replace(interview, status="cancelled", unscheduled_reason_code="STUDENT_WITHDRAWN", unscheduled_reason="Student withdrew; future interview cancelled."))
                continue
        if interview.status == "unscheduled":
            kept.append(interview)
            continue
        if interview.status == "completed" or (interview.scheduled_end is not None and interview.scheduled_end <= now):
            completed = replace(interview, status="completed")
            kept.append(completed)
            occ.add(completed)
            continue
        invalid, reason = classify_invalid(interview, dataset, now, freeze_minutes)
        if students[interview.student_id].withdrawn and interview.scheduled_end is not None and interview.scheduled_end > now:
            cancelled.append(replace(interview, status="cancelled", unscheduled_reason_code="STUDENT_WITHDRAWN", unscheduled_reason="Student withdrew; future interview cancelled."))
        elif invalid:
            repair.append((replace(interview, status="requested", scheduled_start=None, scheduled_end=None, room_id=None, panel_id=None), reason))
        else:
            kept.append(interview)
            occ.add(interview)

    repaired: list[Interview] = []
    unresolved: list[Interview] = []
    repair.sort(key=lambda pair: _rank_key(pair[0], students, companies))
    for interview, reason in repair:
        old = old_by_id.get(interview.id)
        student = students[interview.student_id]
        company = companies[interview.company_id]
        assigned = None
        if old:
            trial = replace(interview, scheduled_start=old.scheduled_start, scheduled_end=old.scheduled_end, room_id=old.room_id, panel_id=old.panel_id, original_start=old.original_start)
            assigned = _same_assignment_possible(trial, dataset, occ)
        if assigned is None and old:
            assigned = _search_slot(
                interview,
                student,
                company,
                panels,
                rooms,
                occ,
                preserve=(old.scheduled_start, old.room_id, old.panel_id),
                max_shift=120,
            )
        if assigned is None:
            assigned = _search_slot(
                interview,
                student,
                company,
                panels,
                rooms,
                occ,
                preserve=(old.scheduled_start if old else None, old.room_id if old else None, old.panel_id if old else None),
            )
        if assigned:
            repaired.append(assigned)
        else:
            code, detail, action = explain_unscheduled(interview, student, company, [p for p in panels if p.company_id == company.id], rooms)
            unresolved.append(
                replace(
                    interview,
                    status="unscheduled",
                    unscheduled_reason_code=code,
                    unscheduled_reason=f"After replan ({reason}): {detail} Suggested action: {action}",
                )
            )

    dataset.interviews = sorted(kept + repaired + unresolved + cancelled, key=lambda i: i.id)
    validation = validate_schedule(dataset)
    metrics = schedule_metrics(dataset, previous)
    changes = []
    moved = 0
    total_shift = 0
    affected_students: set[str] = set()
    affected_companies: set[str] = set()
    affected_rooms: set[str] = set()
    affected_panels: set[str] = set()
    for interview in dataset.interviews:
        old = old_by_id.get(interview.id)
        kind = _change_kind(old, interview)
        shift = 0
        if old and old.scheduled_start is not None and interview.scheduled_start is not None:
            shift = interview.scheduled_start - old.scheduled_start
        if kind != "unchanged":
            affected_students.add(interview.student_id)
            affected_companies.add(interview.company_id)
            if interview.room_id:
                affected_rooms.add(interview.room_id)
            if interview.panel_id:
                affected_panels.add(interview.panel_id)
        if kind == "moved":
            moved += 1
            total_shift += abs(shift)
        changes.append(
            {
                "interview_id": interview.id,
                "classification": kind,
                "old_start": hm(old.scheduled_start) if old and old.scheduled_start is not None else None,
                "new_start": hm(interview.scheduled_start) if interview.scheduled_start is not None else None,
                "old_room": old.room_id if old else None,
                "new_room": interview.room_id,
                "old_panel": old.panel_id if old else None,
                "new_panel": interview.panel_id,
                "shift_minutes": shift,
                "reason": interview.unscheduled_reason or kind,
            }
        )
    changed = [c for c in changes if c["classification"] != "unchanged"]
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    summary = {
        "disruption_description": "; ".join(d.description for d in dataset.disruptions) or "Manual replan",
        "interviews_originally_affected": len(repair) + len(cancelled),
        "interviews_changed": len(changed),
        "unaffected_interviews_preserved": len(changes) - len(changed),
        "interviews_cancelled": len(cancelled),
        "interviews_newly_unscheduled": sum(1 for c in changes if c["classification"] == "newly_unscheduled"),
        "total_shift_minutes": total_shift,
        "average_shift": round(total_shift / moved, 2) if moved else 0,
        "maximum_shift": max([abs(c["shift_minutes"]) for c in changes], default=0),
        "churn_percentage": round(metrics["replan_churn"] * 100, 2),
        "affected_students": len(affected_students),
        "affected_companies": len(affected_companies),
        "affected_rooms": len(affected_rooms),
        "affected_panels": len(affected_panels),
        "duration_ms": duration_ms,
    }
    notifications = {
        "students": [{"id": sid, "why": "Interview changed, cancelled, or unresolved."} for sid in sorted(affected_students)],
        "company_coordinators": [{"id": cid, "why": "Panel schedule or candidate queue changed."} for cid in sorted(affected_companies)],
        "placement_coordinators": [{"id": "placement-team", "why": "Review replan summary and unresolved interviews."}],
        "rooms_facilities": [{"id": rid, "why": "Room assignment or availability changed."} for rid in sorted(affected_rooms)],
    }
    dataset.events.append(
        EventLog(
            id=f"E{len(dataset.events) + 1:04d}",
            timestamp=now,
            event_type="replan_completed",
            payload=summary,
            description=f"Replan completed with {len(changed)} changed appointments and {summary['churn_percentage']}% churn.",
        )
    )
    return {
        "status": "FEASIBLE" if validation["valid"] else "FEASIBLE_WITH_VALIDATION_ERRORS",
        "summary": summary,
        "changes": changes,
        "notifications": notifications,
        "metrics": metrics,
        "validation": validation,
    }
