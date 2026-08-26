from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

InterviewStatus = Literal["requested", "scheduled", "unscheduled", "completed", "cancelled"]
CompanyStatus = Literal["expected", "active", "delayed", "completed"]
ReasonCode = Literal[
    "NO_STUDENT_AVAILABILITY",
    "NO_PANEL_CAPACITY",
    "NO_ROOM_CAPACITY",
    "COMPANY_WINDOW_EXHAUSTED",
    "STUDENT_CONFLICT",
    "PANEL_DROPPED",
    "COMPANY_DELAY",
    "ROOM_UNAVAILABLE",
    "STUDENT_WITHDRAWN",
    "LOWER_PRIORITY_DISPLACED",
    "NO_FEASIBLE_SLOT",
]


@dataclass
class Student:
    id: str
    name: str
    roll_number: str
    branch: str
    cgpa: float
    placement_status: str
    shortlisted_company_ids: list[str]
    available_from: int
    available_until: int
    offer_received: bool = False
    withdrawn: bool = False
    priority_score: float = 0.0


@dataclass
class Company:
    id: str
    name: str
    priority_tier: int
    company_type: str
    day_preference: int
    cgpa_cutoff: float
    eligible_branches: list[str]
    shortlist_size: int
    interview_duration: int
    panel_count: int
    preferred_start: int
    available_start: int
    available_end: int
    expected_arrival: int
    status: CompanyStatus = "expected"


@dataclass
class Panel:
    id: str
    company_id: str
    name: str
    active: bool
    available_from: int
    available_until: int


@dataclass
class Room:
    id: str
    name: str
    building: str
    floor: int
    available: bool
    available_from: int
    available_until: int
    room_type: str = "interview"
    outage_windows: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class Interview:
    id: str
    student_id: str
    company_id: str
    duration: int
    priority: int
    status: InterviewStatus = "requested"
    scheduled_start: int | None = None
    scheduled_end: int | None = None
    room_id: str | None = None
    panel_id: str | None = None
    original_start: int | None = None
    locked: bool = False
    unscheduled_reason: str | None = None
    unscheduled_reason_code: str | None = None


@dataclass
class Disruption:
    id: str
    kind: str
    effective_time: int
    payload: dict[str, Any]
    description: str


@dataclass
class EventLog:
    id: str
    timestamp: int
    event_type: str
    payload: dict[str, Any]
    description: str


@dataclass
class Dataset:
    seed: int
    students: list[Student]
    companies: list[Company]
    panels: list[Panel]
    rooms: list[Room]
    interviews: list[Interview]
    disruptions: list[Disruption] = field(default_factory=list)
    events: list[EventLog] = field(default_factory=list)
    current_time: int = 9 * 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "students": [asdict(x) for x in self.students],
            "companies": [asdict(x) for x in self.companies],
            "panels": [asdict(x) for x in self.panels],
            "rooms": [asdict(x) for x in self.rooms],
            "interviews": [asdict(x) for x in self.interviews],
            "disruptions": [asdict(x) for x in self.disruptions],
            "events": [asdict(x) for x in self.events],
            "current_time": self.current_time,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Dataset":
        return Dataset(
            seed=data["seed"],
            students=[Student(**x) for x in data["students"]],
            companies=[Company(**x) for x in data["companies"]],
            panels=[Panel(**x) for x in data["panels"]],
            rooms=[Room(**x) for x in data["rooms"]],
            interviews=[Interview(**x) for x in data["interviews"]],
            disruptions=[Disruption(**x) for x in data.get("disruptions", [])],
            events=[EventLog(**x) for x in data.get("events", [])],
            current_time=data.get("current_time", 9 * 60),
        )

