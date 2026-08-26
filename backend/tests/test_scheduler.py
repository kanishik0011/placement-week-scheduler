from dataclasses import replace

from app.generator import generate_dataset
from app.models import Company, Dataset, Interview, Panel, Room, Student
from app.scheduler.engine import schedule_dataset
from app.scheduler.validator import validate_schedule
from app.time_utils import at, day_end, day_start


def test_default_schedule_validates():
    dataset = generate_dataset(42)
    result = schedule_dataset(dataset)
    validation = validate_schedule(dataset)
    assert result["scheduled"] > 0
    assert validation["valid"], validation["violations"][:5]
    assert all(i.unscheduled_reason for i in dataset.interviews if i.status == "unscheduled")


def test_impossible_dataset_reports_reasons():
    student = Student("S1", "A Test", "R1", "CSE", 9.1, "eligible", ["C1"], day_start(1), day_end(1))
    company = Company("C1", "Tiny Window", 1, "premium/product", 1, 8.0, ["CSE"], 2, 60, 1, at(1, 9), at(1, 9), at(1, 9, 30), at(1, 9))
    panel = Panel("P1", "C1", "Tiny Window Panel", True, at(1, 9), at(1, 9, 30))
    room = Room("R1", "Room", "Block", 1, True, day_start(1), day_end(1))
    dataset = Dataset(1, [student], [company], [panel], [room], [Interview("I1", "S1", "C1", 60, 1)])
    result = schedule_dataset(dataset)
    assert result["unscheduled"] == 1
    assert dataset.interviews[0].unscheduled_reason_code is not None

