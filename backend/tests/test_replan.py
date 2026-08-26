from dataclasses import replace

from app.generator import generate_dataset
from app.scheduler.engine import schedule_dataset
from app.scheduler.replan import replan_dataset
from app.scheduler.validator import validate_schedule
from app.services.disruptions import company_delay, day1_crisis, panel_drop, room_unavailable, set_clock, student_withdrawal
from app.time_utils import at, overlaps


def _scheduled(dataset):
    return [i for i in dataset.interviews if i.status == "scheduled" and i.scheduled_start is not None]


def test_company_delay_repairs_or_marks_unresolved_with_low_churn():
    dataset = generate_dataset(42)
    schedule_dataset(dataset)
    set_clock(dataset, at(1, 10))
    company = max([c for c in dataset.companies if c.day_preference == 1], key=lambda c: c.shortlist_size)
    before = [replace(i) for i in dataset.interviews]
    company_delay(dataset, company.id, 180)
    result = replan_dataset(dataset)
    assert validate_schedule(dataset)["valid"]
    assert all(i.scheduled_start >= company.available_start for i in dataset.interviews if i.company_id == company.id and i.status == "scheduled")
    assert result["summary"]["churn_percentage"] < 40
    assert sum(1 for old in before if old.status == "scheduled") > 0


def test_panel_drop_removes_future_assignments_from_inactive_panel():
    dataset = generate_dataset(42)
    schedule_dataset(dataset)
    set_clock(dataset, at(1, 10))
    target = next(i for i in _scheduled(dataset) if i.scheduled_start > dataset.current_time and i.panel_id)
    panel_drop(dataset, target.panel_id)
    replan_dataset(dataset)
    assert validate_schedule(dataset)["valid"]
    assert all(i.panel_id != target.panel_id for i in dataset.interviews if i.status == "scheduled" and i.scheduled_start and i.scheduled_start > dataset.current_time)


def test_student_withdrawal_cancels_future_and_keeps_completed():
    dataset = generate_dataset(42)
    schedule_dataset(dataset)
    target = next(i for i in _scheduled(dataset))
    set_clock(dataset, (target.scheduled_end or 0) + 1)
    student_withdrawal(dataset, target.student_id)
    replan_dataset(dataset)
    assert any(i.id == target.id and i.status == "completed" for i in dataset.interviews)
    assert all(i.status in {"completed", "cancelled"} for i in dataset.interviews if i.student_id == target.student_id)


def test_room_outage_has_zero_overlap_after_replan():
    dataset = generate_dataset(42)
    schedule_dataset(dataset)
    set_clock(dataset, at(1, 10))
    target = next(i for i in _scheduled(dataset) if i.scheduled_start > dataset.current_time and i.room_id)
    room_unavailable(dataset, target.room_id, target.scheduled_start, target.scheduled_end)
    replan_dataset(dataset)
    assert validate_schedule(dataset)["valid"]
    for interview in dataset.interviews:
        if interview.status == "scheduled" and interview.room_id == target.room_id:
            assert not overlaps(interview.scheduled_start, interview.scheduled_end, target.scheduled_start, target.scheduled_end)


def test_defense_scenario_validates():
    dataset = generate_dataset(42)
    schedule_dataset(dataset)
    set_clock(dataset, at(1, 10, 30))
    day1_crisis(dataset)
    result = replan_dataset(dataset)
    assert validate_schedule(dataset)["valid"]
    assert result["summary"]["interviews_originally_affected"] >= 1
    assert "notifications" in result

