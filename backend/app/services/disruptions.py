from __future__ import annotations

from dataclasses import replace

from app.models import Dataset, Disruption, EventLog
from app.time_utils import hm


def _next_id(prefix: str, count: int) -> str:
    return f"{prefix}{count + 1:04d}"


def set_clock(dataset: Dataset, current_time: int) -> Dataset:
    dataset.current_time = current_time
    dataset.events.append(
        EventLog(
            id=_next_id("E", len(dataset.events)),
            timestamp=current_time,
            event_type="clock_set",
            payload={"current_time": current_time},
            description=f"Simulation clock set to {hm(current_time)}.",
        )
    )
    return dataset


def company_delay(dataset: Dataset, company_id: str, delay_minutes: int, effective_time: int | None = None) -> Disruption:
    effective_time = dataset.current_time if effective_time is None else effective_time
    company = next(c for c in dataset.companies if c.id == company_id)
    company.available_start = max(company.available_start, company.expected_arrival + delay_minutes, effective_time)
    company.status = "delayed"
    disruption = Disruption(
        id=_next_id("D", len(dataset.disruptions)),
        kind="company_delay",
        effective_time=effective_time,
        payload={"company_id": company_id, "delay_minutes": delay_minutes, "new_available_start": company.available_start},
        description=f"{company.name} delayed by {delay_minutes} minutes; earliest interviews now {hm(company.available_start)}.",
    )
    dataset.disruptions.append(disruption)
    dataset.events.append(EventLog(_next_id("E", len(dataset.events)), effective_time, "company_delayed", disruption.payload, disruption.description))
    return disruption


def panel_drop(dataset: Dataset, panel_id: str, effective_time: int | None = None) -> Disruption:
    effective_time = dataset.current_time if effective_time is None else effective_time
    panel = next(p for p in dataset.panels if p.id == panel_id)
    panel.active = False
    disruption = Disruption(
        id=_next_id("D", len(dataset.disruptions)),
        kind="panel_drop",
        effective_time=effective_time,
        payload={"panel_id": panel_id},
        description=f"{panel.name} dropped from service effective {hm(effective_time)}.",
    )
    dataset.disruptions.append(disruption)
    dataset.events.append(EventLog(_next_id("E", len(dataset.events)), effective_time, "panel_dropped", disruption.payload, disruption.description))
    return disruption


def student_withdrawal(dataset: Dataset, student_id: str, effective_time: int | None = None, reason: str = "Student withdrew") -> Disruption:
    effective_time = dataset.current_time if effective_time is None else effective_time
    student = next(s for s in dataset.students if s.id == student_id)
    student.withdrawn = True
    student.placement_status = "withdrawn"
    disruption = Disruption(
        id=_next_id("D", len(dataset.disruptions)),
        kind="student_withdrawal",
        effective_time=effective_time,
        payload={"student_id": student_id, "reason": reason},
        description=f"{student.name} withdrew effective {hm(effective_time)}.",
    )
    dataset.disruptions.append(disruption)
    dataset.events.append(EventLog(_next_id("E", len(dataset.events)), effective_time, "student_withdrawn", disruption.payload, disruption.description))
    return disruption


def room_unavailable(dataset: Dataset, room_id: str, start: int, end: int) -> Disruption:
    room = next(r for r in dataset.rooms if r.id == room_id)
    room.outage_windows.append((start, end))
    disruption = Disruption(
        id=_next_id("D", len(dataset.disruptions)),
        kind="room_unavailable",
        effective_time=start,
        payload={"room_id": room_id, "start": start, "end": end},
        description=f"{room.name} unavailable from {hm(start)} to {hm(end)}.",
    )
    dataset.disruptions.append(disruption)
    dataset.events.append(EventLog(_next_id("E", len(dataset.events)), dataset.current_time, "room_unavailable", disruption.payload, disruption.description))
    return disruption


def day1_crisis(dataset: Dataset, withdraw_count: int = 15) -> list[Disruption]:
    day1 = [c for c in dataset.companies if c.day_preference == 1]
    largest = max(day1, key=lambda c: c.shortlist_size)
    disruptions = [company_delay(dataset, largest.id, 180)]
    panel = next(p for p in dataset.panels if p.company_id == largest.id and p.active)
    disruptions.append(panel_drop(dataset, panel.id))
    scheduled = [
        i for i in dataset.interviews
        if i.company_id == largest.id and i.status == "scheduled" and i.scheduled_start and i.scheduled_start > dataset.current_time
    ]
    seen: set[str] = set()
    for interview in scheduled:
        if len(seen) >= withdraw_count:
            break
        if interview.student_id not in seen:
            disruptions.append(student_withdrawal(dataset, interview.student_id, reason="Defense Day-1 crisis scenario"))
            seen.add(interview.student_id)
    return disruptions

