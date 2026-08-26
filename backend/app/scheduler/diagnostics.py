from __future__ import annotations

from app.models import Company, Interview, Panel, Room, Student
from app.time_utils import hm


def explain_unscheduled(
    interview: Interview,
    student: Student,
    company: Company,
    panels: list[Panel],
    rooms: list[Room],
) -> tuple[str, str, str]:
    if student.withdrawn:
        return "STUDENT_WITHDRAWN", f"{student.name} has withdrawn from future interviews.", "Confirm withdrawal or restore student availability."
    if company.id not in student.shortlisted_company_ids:
        return "NO_FEASIBLE_SLOT", "Student is not on this company's shortlist.", "Review shortlist import."
    if not any(p.active for p in panels):
        return "PANEL_DROPPED", f"All panels for {company.name} are inactive.", "Reactivate a panel or add panel capacity."
    if company.available_start >= company.available_end:
        return "COMPANY_WINDOW_EXHAUSTED", f"{company.name} has no remaining availability window.", "Extend company availability."
    if not any(r.available for r in rooms):
        return "NO_ROOM_CAPACITY", "No interview rooms are currently available.", "Open additional rooms."
    active_panel_minutes = sum(max(0, p.available_until - max(p.available_from, company.available_start)) for p in panels if p.active)
    if active_panel_minutes < interview.duration:
        return "NO_PANEL_CAPACITY", f"No active {company.name} panel has {interview.duration} minutes available.", "Add panels or shorten interviews."
    return (
        "NO_FEASIBLE_SLOT",
        f"No feasible {interview.duration}-minute slot for {student.name} and {company.name} within {hm(company.available_start)}-{hm(company.available_end)}.",
        "Consider extending the company window, adding panels/rooms, or manually prioritizing lower-priority displacement.",
    )

