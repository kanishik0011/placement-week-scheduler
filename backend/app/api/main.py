from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import StateStore
from app.generator import generate_dataset
from app.scheduler.engine import schedule_dataset
from app.scheduler.metrics import schedule_metrics
from app.scheduler.replan import replan_dataset
from app.scheduler.validator import validate_schedule
from app.services import disruptions
from app.time_utils import at

DEFAULT_DB_PATH = "/tmp/placement_scheduler.sqlite3" if os.getenv("VERCEL") else "data/placement_scheduler.sqlite3"
DB_PATH = Path(os.getenv("PLACEMENT_DB", DEFAULT_DB_PATH))
store = StateStore(DB_PATH)
app = FastAPI(title="Placement Week Scheduler API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SeedRequest(BaseModel):
    seed: int = 42


class ClockRequest(BaseModel):
    day: int = 1
    hour: int = 10
    minute: int = 0


class CompanyDelayRequest(BaseModel):
    company_id: str
    delay_minutes: int = 180


class PanelDropRequest(BaseModel):
    panel_id: str


class StudentWithdrawalRequest(BaseModel):
    student_id: str
    reason: str = "Coordinator marked student withdrawn"


class RoomUnavailableRequest(BaseModel):
    room_id: str
    day: int = 1
    start_hour: int = 12
    start_minute: int = 0
    end_hour: int = 14
    end_minute: int = 0


def _save_and_summary(dataset) -> dict[str, Any]:
    store.save(dataset)
    return {"dataset": dataset.to_dict(), "metrics": schedule_metrics(dataset)}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "placement-week-scheduler"}


@app.post("/dataset/generate")
def dataset_generate(req: SeedRequest) -> dict[str, Any]:
    dataset = generate_dataset(req.seed)
    store.save(dataset)
    return {"summary": {"seed": req.seed, "students": len(dataset.students), "companies": len(dataset.companies), "rooms": len(dataset.rooms), "interviews": len(dataset.interviews)}}


@app.get("/dataset/summary")
def dataset_summary() -> dict[str, Any]:
    dataset = store.load()
    return {"seed": dataset.seed, "students": len(dataset.students), "companies": len(dataset.companies), "rooms": len(dataset.rooms), "panels": len(dataset.panels), "interviews": len(dataset.interviews), "current_time": dataset.current_time}


@app.get("/students")
def students() -> list[dict[str, Any]]:
    return [s.__dict__ for s in store.load().students]


@app.get("/companies")
def companies() -> list[dict[str, Any]]:
    return [c.__dict__ for c in store.load().companies]


@app.get("/rooms")
def rooms() -> list[dict[str, Any]]:
    return [r.__dict__ for r in store.load().rooms]


@app.get("/panels")
def panels() -> list[dict[str, Any]]:
    return [p.__dict__ for p in store.load().panels]


@app.post("/clock")
def clock(req: ClockRequest) -> dict[str, Any]:
    dataset = store.load()
    disruptions.set_clock(dataset, at(req.day, req.hour, req.minute))
    store.save(dataset)
    return {"current_time": dataset.current_time}


@app.post("/schedule/generate")
def schedule_generate() -> dict[str, Any]:
    dataset = store.load()
    result = schedule_dataset(dataset)
    store.save(dataset)
    return result


@app.get("/schedule")
def schedule() -> list[dict[str, Any]]:
    return [i.__dict__ for i in store.load().interviews]


@app.get("/schedule/metrics")
def metrics() -> dict[str, Any]:
    return schedule_metrics(store.load())


@app.post("/schedule/validate")
def validate() -> dict[str, Any]:
    return validate_schedule(store.load())


@app.post("/disruptions/company-delay")
def disrupt_company_delay(req: CompanyDelayRequest) -> dict[str, Any]:
    dataset = store.load()
    event = disruptions.company_delay(dataset, req.company_id, req.delay_minutes)
    store.save(dataset)
    return event.__dict__


@app.post("/disruptions/panel-drop")
def disrupt_panel_drop(req: PanelDropRequest) -> dict[str, Any]:
    dataset = store.load()
    event = disruptions.panel_drop(dataset, req.panel_id)
    store.save(dataset)
    return event.__dict__


@app.post("/disruptions/student-withdrawal")
def disrupt_student_withdrawal(req: StudentWithdrawalRequest) -> dict[str, Any]:
    dataset = store.load()
    event = disruptions.student_withdrawal(dataset, req.student_id, reason=req.reason)
    store.save(dataset)
    return event.__dict__


@app.post("/disruptions/room-unavailable")
def disrupt_room_unavailable(req: RoomUnavailableRequest) -> dict[str, Any]:
    dataset = store.load()
    event = disruptions.room_unavailable(dataset, req.room_id, at(req.day, req.start_hour, req.start_minute), at(req.day, req.end_hour, req.end_minute))
    store.save(dataset)
    return event.__dict__


@app.get("/disruptions")
def list_disruptions() -> list[dict[str, Any]]:
    return [d.__dict__ for d in store.load().disruptions]


@app.post("/disruptions/day1-crisis")
def disrupt_day1_crisis() -> dict[str, Any]:
    dataset = store.load()
    events = disruptions.day1_crisis(dataset)
    store.save(dataset)
    return {"disruptions": [e.__dict__ for e in events]}


@app.post("/replan")
def replan() -> dict[str, Any]:
    dataset = store.load()
    result = replan_dataset(dataset)
    replan_id = store.save_replan(result)
    store.save(dataset)
    return {"id": replan_id, **result}


@app.get("/replans/latest")
def latest_replan() -> dict[str, Any]:
    result = store.load_latest_replan()
    if result is None:
        raise HTTPException(status_code=404, detail="No replan has been run")
    return result


@app.get("/replans/{replan_id}")
def get_replan(replan_id: int) -> dict[str, Any]:
    try:
        return store.load_replan(replan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Replan not found") from exc


@app.get("/replans/{replan_id}/diff")
def get_replan_diff(replan_id: int) -> dict[str, Any]:
    result = get_replan(replan_id)
    return {"summary": result["summary"], "changes": result["changes"], "notifications": result["notifications"]}


@app.get("/events")
def events() -> list[dict[str, Any]]:
    return [e.__dict__ for e in store.load().events[-50:]]
