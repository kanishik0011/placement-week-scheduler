from __future__ import annotations

from dataclasses import dataclass

SLOT_MINUTES = 5
DAY_MINUTES = 24 * 60
OPERATING_START = 9 * 60
OPERATING_END = 18 * 60
DEFAULT_FREEZE_MINUTES = 30


def day_start(day: int) -> int:
    return (day - 1) * DAY_MINUTES + OPERATING_START


def day_end(day: int) -> int:
    return (day - 1) * DAY_MINUTES + OPERATING_END


def at(day: int, hour: int, minute: int = 0) -> int:
    return (day - 1) * DAY_MINUTES + hour * 60 + minute


def day_of(value: int) -> int:
    return value // DAY_MINUTES + 1


def hm(value: int) -> str:
    minutes = value % DAY_MINUTES
    return f"D{day_of(value)} {minutes // 60:02d}:{minutes % 60:02d}"


def align_slot(value: int) -> int:
    return value + ((SLOT_MINUTES - value % SLOT_MINUTES) % SLOT_MINUTES)


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


@dataclass(frozen=True)
class Window:
    start: int
    end: int

    def contains(self, start: int, end: int) -> bool:
        return self.start <= start and end <= self.end

