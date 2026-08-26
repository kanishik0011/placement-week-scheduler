from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import replace
from typing import Any

from app.models import Company, Dataset, EventLog, Interview, Panel, Room, Student
from app.scheduler.diagnostics import explain_unscheduled
from app.scheduler.policy import TIER_WEIGHTS
from app.scheduler.validator import validate_schedule
from app.time_utils import SLOT_MINUTES, align_slot, day_end, day_start, overlaps


class Occupancy:
    def __init__(self) -> None:
        self.student: dict[str, set[int]] = defaultdict(set)
        self.panel: dict[str, set[int]] = defaultdict(set)
        self.room: dict[str, set[int]] = defaultdict(set)

    @staticmethod
    def _slots(start: int, end: int) -> range:
        return range(start // SLOT_MINUTES, end // SLOT_MINUTES)

    def add(self, interview: Interview) -> None:
        if interview.scheduled_start is None or interview.scheduled_end is None:
            return
        slots = set(self._slots(interview.scheduled_start, interview.scheduled_end))
        self.student[interview.student_id].update(slots)
        if interview.panel_id:
            self.panel[interview.panel_id].update(slots)
        if interview.room_id:
            self.room[interview.room_id].update(slots)

    def free(self, kind: str, key: str, start: int, end: int) -> bool:
        occupied = getattr(self, kind).get(key, set())
        return not any(slot in occupied for slot in self._slots(start, end))


def _is_room_usable(room: Room, start: int, end: int) -> bool:
    return (
        room.available
        and room.available_from <= start
        and end <= room.available_until
        and all(not overlaps(start, end, a, b) for a, b in room.outage_windows)
    )


def _can_assign(
    interview: Interview,
    start: int,
    panel: Panel,
    room: Room,
    student: Student,
    company: Company,
    occ: Occupancy,
) -> bool:
    end = start + interview.duration
    if student.withdrawn:
        return False
    if company.id not in student.shortlisted_company_ids:
        return False
    if not panel.active or panel.company_id != company.id:
        return False
    if start < max(company.available_start, panel.available_from, student.available_from, room.available_from):
        return False
    if end > min(company.available_end, panel.available_until, student.available_until, room.available_until):
        return False
    if start < day_start(company.day_preference) or end > day_end(company.day_preference):
        return False
    if not _is_room_usable(room, start, end):
        return False
    return occ.free("student", student.id, start, end) and occ.free("panel", panel.id, start, end) and occ.free("room", room.id, start, end)


def _can_student_panel_time(
    interview: Interview,
    start: int,
    panel: Panel,
    student: Student,
    company: Company,
    occ: Occupancy,
) -> bool:
    end = start + interview.duration
    if student.withdrawn or company.id not in student.shortlisted_company_ids:
        return False
    if not panel.active or panel.company_id != company.id:
        return False
    if start < max(company.available_start, panel.available_from, student.available_from):
        return False
    if end > min(company.available_end, panel.available_until, student.available_until):
        return False
    if start < day_start(company.day_preference) or end > day_end(company.day_preference):
        return False
    return occ.free("student", student.id, start, end) and occ.free("panel", panel.id, start, end)


def _assign(interview: Interview, start: int, panel: Panel, room: Room, occ: Occupancy, status: str = "scheduled") -> Interview:
    updated = replace(
        interview,
        status=status,
        scheduled_start=start,
        scheduled_end=start + interview.duration,
        room_id=room.id,
        panel_id=panel.id,
        original_start=interview.original_start if interview.original_start is not None else start,
        unscheduled_reason=None,
        unscheduled_reason_code=None,
    )
    occ.add(updated)
    return updated


def _search_slot(
    interview: Interview,
    student: Student,
    company: Company,
    panels: list[Panel],
    rooms: list[Room],
    occ: Occupancy,
    preferred_start: int | None = None,
    preserve: tuple[int | None, str | None, str | None] | None = None,
    max_shift: int | None = None,
) -> Interview | None:
    active_panels = [p for p in panels if p.company_id == company.id and p.active]
    if not active_panels:
        return None
    earliest = align_slot(max(company.available_start, student.available_from, day_start(company.day_preference)))
    latest = min(company.available_end, student.available_until, day_end(company.day_preference)) - interview.duration
    if latest < earliest:
        return None

    base = preferred_start if preferred_start is not None else company.preferred_start
    if preserve and preserve[0] is not None:
        base = preserve[0]

    starts = list(range(earliest, latest + 1, SLOT_MINUTES))
    starts.sort(key=lambda s: (abs(s - base), s))
    if max_shift is not None and preserve and preserve[0] is not None:
        starts = [s for s in starts if abs(s - preserve[0]) <= max_shift]
    if preserve:
        old_start, old_room_id, old_panel_id = preserve
        if old_start is not None and earliest <= old_start <= latest:
            starts = [old_start] + [s for s in starts if s != old_start]
        active_panels.sort(key=lambda p: 0 if p.id == old_panel_id else 1)
        rooms = sorted(rooms, key=lambda r: 0 if r.id == old_room_id else 1)

    for start in starts:
        for panel in active_panels:
            if not _can_student_panel_time(interview, start, panel, student, company, occ):
                continue
            for room in rooms:
                end = start + interview.duration
                if _is_room_usable(room, start, end) and occ.free("room", room.id, start, end):
                    return _assign(interview, start, panel, room, occ)
    return None


def _search_slot_forward(
    interview: Interview,
    student: Student,
    company: Company,
    panels: list[Panel],
    rooms: list[Room],
    occ: Occupancy,
    panel_cursors: dict[str, int],
) -> Interview | None:
    active_panels = [p for p in panels if p.company_id == company.id and p.active]
    if not active_panels:
        return None
    active_panels.sort(key=lambda p: panel_cursors.get(p.id, max(company.available_start, p.available_from)))
    latest = min(company.available_end, student.available_until, day_end(company.day_preference)) - interview.duration
    for panel in active_panels:
        earliest = align_slot(max(company.available_start, panel.available_from, student.available_from, day_start(company.day_preference), panel_cursors.get(panel.id, company.available_start)))
        if latest < earliest:
            continue
        start = earliest
        while start <= latest:
            if _can_student_panel_time(interview, start, panel, student, company, occ):
                end = start + interview.duration
                for room in rooms:
                    if _is_room_usable(room, start, end) and occ.free("room", room.id, start, end):
                        assigned = _assign(interview, start, panel, room, occ)
                        panel_cursors[panel.id] = end
                        return assigned
            start += SLOT_MINUTES
    return None


def _rank_key(interview: Interview, students: dict[str, Student], companies: dict[str, Company]) -> tuple:
    company = companies[interview.company_id]
    student = students[interview.student_id]
    pressure = len(student.shortlisted_company_ids)
    return (company.priority_tier, -TIER_WEIGHTS[company.priority_tier], -pressure, -student.cgpa, company.day_preference, company.preferred_start)


def schedule_dataset(dataset: Dataset) -> dict[str, Any]:
    started = time.perf_counter()
    students = {s.id: s for s in dataset.students}
    companies = {c.id: c for c in dataset.companies}
    panels = dataset.panels
    rooms = dataset.rooms
    occ = Occupancy()
    panel_cursors = {p.id: max(p.available_from, companies[p.company_id].available_start) for p in panels}
    scheduled: list[Interview] = []
    unscheduled: list[Interview] = []

    raw_requested = [replace(i, status="requested", scheduled_start=None, scheduled_end=None, room_id=None, panel_id=None, original_start=None) for i in dataset.interviews]
    grouped: dict[str, list[Interview]] = defaultdict(list)
    for interview in raw_requested:
        grouped[interview.company_id].append(interview)
    requested: list[Interview] = []
    capacity_pruned: list[Interview] = []
    for company_id, items in grouped.items():
        company = companies[company_id]
        company_panels = [p for p in panels if p.company_id == company_id and p.active]
        panel_minutes = sum(max(0, min(p.available_until, company.available_end) - max(p.available_from, company.available_start)) for p in company_panels)
        theoretical_capacity = max(1, panel_minutes // max(1, company.interview_duration))
        search_budget = min(len(items), int(theoretical_capacity * 1.25) + 8)
        items.sort(key=lambda i: _rank_key(i, students, companies))
        requested.extend(items[:search_budget])
        for item in items[search_budget:]:
            capacity_pruned.append(
                replace(
                    item,
                    status="unscheduled",
                    unscheduled_reason_code="NO_PANEL_CAPACITY",
                    unscheduled_reason=(
                        f"{company.name} requested {len(items)} interviews but has theoretical panel capacity "
                        f"for about {theoretical_capacity}. Suggested action: add panels, extend the window, or approve priority-based displacement."
                    ),
                )
            )
    requested.sort(key=lambda i: _rank_key(i, students, companies))
    for interview in requested:
        student = students[interview.student_id]
        company = companies[interview.company_id]
        assigned = _search_slot_forward(interview, student, company, panels, rooms, occ, panel_cursors)
        if assigned:
            scheduled.append(assigned)
        else:
            code, reason, action = explain_unscheduled(interview, student, company, [p for p in panels if p.company_id == company.id], rooms)
            unscheduled.append(replace(interview, status="unscheduled", unscheduled_reason_code=code, unscheduled_reason=f"{reason} Suggested action: {action}"))

    dataset.interviews = sorted(scheduled + unscheduled + capacity_pruned, key=lambda i: i.id)
    validation = validate_schedule(dataset)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    dataset.events.append(
        EventLog(
            id=f"E{len(dataset.events) + 1:04d}",
            timestamp=dataset.current_time,
            event_type="schedule_generated",
            payload={"scheduled": len(scheduled), "unscheduled": len(unscheduled) + len(capacity_pruned), "duration_ms": duration_ms, "valid": validation["valid"]},
            description=f"Generated schedule: {len(scheduled)} scheduled, {len(unscheduled) + len(capacity_pruned)} unresolved.",
        )
    )
    return {
        "status": "FEASIBLE" if scheduled else "INFEASIBLE",
        "solver": "deterministic_candidate_heuristic",
        "duration_ms": duration_ms,
        "scheduled": len(scheduled),
        "unscheduled": len(unscheduled) + len(capacity_pruned),
        "validation": validation,
    }
