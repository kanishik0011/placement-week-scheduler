from __future__ import annotations

import argparse
import json
from dataclasses import replace

from app.generator import generate_dataset
from app.scheduler.engine import schedule_dataset
from app.scheduler.metrics import schedule_metrics
from app.scheduler.replan import replan_dataset
from app.scheduler.validator import validate_schedule
from app.services.disruptions import day1_crisis, set_clock
from app.time_utils import at


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic defense backup demo.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dataset = generate_dataset(args.seed)
    schedule_result = schedule_dataset(dataset)
    before_interviews = [replace(i) for i in dataset.interviews]
    before = schedule_metrics(dataset)
    largest_day1 = max([c for c in dataset.companies if c.day_preference == 1], key=lambda c: c.shortlist_size)
    set_clock(dataset, at(1, 10, 30))
    disruptions = day1_crisis(dataset)
    replan = replan_dataset(dataset)
    after = schedule_metrics(dataset, before_interviews)
    payload = {
        "initial_schedule": schedule_result,
        "largest_day1_recruiter": {"id": largest_day1.id, "name": largest_day1.name, "shortlist_size": largest_day1.shortlist_size},
        "before_metrics": before,
        "disruptions": [d.__dict__ for d in disruptions],
        "replan_summary": replan["summary"],
        "after_metrics": after,
        "affected_interviews": replan["summary"]["interviews_originally_affected"],
        "moved_interviews": sum(1 for c in replan["changes"] if c["classification"] == "moved"),
        "unchanged_interviews": sum(1 for c in replan["changes"] if c["classification"] == "unchanged"),
        "unscheduled_interviews": after["unscheduled_interviews"],
        "churn_percentage": replan["summary"]["churn_percentage"],
        "maximum_shift": replan["summary"]["maximum_shift"],
        "validation": validate_schedule(dataset),
        "solver_duration_ms": replan["summary"]["duration_ms"],
        "diff_sample": [c for c in replan["changes"] if c["classification"] != "unchanged"][:20],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

