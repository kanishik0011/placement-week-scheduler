from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models import Dataset, Interview
from app.time_utils import OPERATING_END, OPERATING_START, day_of, overlaps


def _scheduled(interviews: list[Interview]) -> list[Interview]:
    return [i for i in interviews if i.status in {"scheduled", "completed"} and i.scheduled_start is not None and i.scheduled_end is not None]


def validate_schedule(dataset: Dataset) -> dict[str, Any]:
    students = {s.id: s for s in dataset.students}
    companies = {c.id: c for c in dataset.companies}
    panels = {p.id: p for p in dataset.panels}
    rooms = {r.id: r for r in dataset.rooms}
    violations: list[dict[str, Any]] = []

    for interview in _scheduled(dataset.interviews):
        student = students.get(interview.student_id)
        company = companies.get(interview.company_id)
        panel = panels.get(interview.panel_id or "")
        room = rooms.get(interview.room_id or "")
        start = interview.scheduled_start
        end = interview.scheduled_end
        if not student or not company or not panel or not room:
            violations.append({"interview_id": interview.id, "code": "MISSING_REFERENCE", "message": "Interview references missing resource."})
            continue
        if student.withdrawn and interview.status != "completed":
            violations.append({"interview_id": interview.id, "code": "STUDENT_WITHDRAWN", "message": "Withdrawn student has a future scheduled interview."})
        if company.id not in student.shortlisted_company_ids:
            violations.append({"interview_id": interview.id, "code": "NOT_SHORTLISTED", "message": "Student is not shortlisted by company."})
        if panel.company_id != company.id:
            violations.append({"interview_id": interview.id, "code": "PANEL_COMPANY", "message": "Assigned panel does not belong to company."})
        if not panel.active and interview.status != "completed":
            violations.append({"interview_id": interview.id, "code": "PANEL_DROPPED", "message": "Inactive panel has future interview."})
        if not room.available:
            violations.append({"interview_id": interview.id, "code": "ROOM_UNAVAILABLE", "message": "Unavailable room has interview."})
        if end - start != interview.duration:
            violations.append({"interview_id": interview.id, "code": "BAD_DURATION", "message": "Scheduled duration does not match company duration."})
        if start < company.available_start or end > company.available_end:
            violations.append({"interview_id": interview.id, "code": "COMPANY_WINDOW", "message": "Interview outside company availability."})
        if start < panel.available_from or end > panel.available_until:
            violations.append({"interview_id": interview.id, "code": "PANEL_WINDOW", "message": "Interview outside panel availability."})
        if start < room.available_from or end > room.available_until:
            violations.append({"interview_id": interview.id, "code": "ROOM_WINDOW", "message": "Interview outside room availability."})
        if start < student.available_from or end > student.available_until:
            violations.append({"interview_id": interview.id, "code": "STUDENT_WINDOW", "message": "Interview outside student availability."})
        if (start % (24 * 60)) < OPERATING_START or (end % (24 * 60)) > OPERATING_END or day_of(start) != day_of(end - 1):
            violations.append({"interview_id": interview.id, "code": "OPERATING_HOURS", "message": "Interview outside operating hours."})
        for outage_start, outage_end in room.outage_windows:
            if overlaps(start, end, outage_start, outage_end):
                violations.append({"interview_id": interview.id, "code": "ROOM_OUTAGE", "message": "Interview overlaps a room outage."})

    for field in ["student_id", "room_id", "panel_id"]:
        grouped: dict[str, list[Interview]] = defaultdict(list)
        for interview in _scheduled(dataset.interviews):
            key = getattr(interview, field)
            if key:
                grouped[key].append(interview)
        for key, values in grouped.items():
            values.sort(key=lambda x: x.scheduled_start or 0)
            for left, right in zip(values, values[1:]):
                if overlaps(left.scheduled_start or 0, left.scheduled_end or 0, right.scheduled_start or 0, right.scheduled_end or 0):
                    violations.append(
                        {
                            "interview_id": right.id,
                            "code": f"{field.upper()}_OVERLAP",
                            "message": f"{field} {key} has overlapping interviews {left.id} and {right.id}.",
                        }
                    )

    return {"valid": not violations, "violations": violations, "violation_count": len(violations)}

