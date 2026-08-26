# Placement Week Scheduler

## Problem

This project replaces a placement coordinator's physical whiteboard during a 4-day engineering-college placement week. It generates a deterministic but realistic 800-student, 35-company, 20-room dataset, builds a feasible interview schedule, exposes unresolved interviews with reasons, handles live disruptions, and replans with minimal churn.

## Architecture

```text
Next.js Dashboard
  |
  v
FastAPI REST API
  |
  +-- SQLite snapshot persistence
  |
  v
Scheduling Engine
  +-- Dataset Generator
  +-- Candidate-slot Scheduler
  +-- Minimal-churn Replanner
  +-- Independent Validator
  +-- Metrics and Diagnostics
```

The backend domain logic lives outside HTTP handlers, so tests and the CLI can call the scheduler directly.

## Scheduling model

Time is represented internally as integer minutes from placement-week start, aligned to 5-minute slots. The scheduler ranks high-priority and highly constrained interviews first, then assigns them to a valid company panel, student, and room slot. It uses forward panel cursors for performance and independent validation after every schedule/replan.

Hard constraints never bend: no overlapping student, room, or panel use; panel must belong to the company; windows and operating hours must hold; withdrawn students, delayed companies, dropped panels, and room outages are enforced.

When capacity is impossible, interviews are not discarded. They are marked `unscheduled` with reason codes such as `NO_PANEL_CAPACITY`, `ROOM_UNAVAILABLE`, `STUDENT_WITHDRAWN`, and `NO_FEASIBLE_SLOT`.

## What is a good schedule?

Metrics include coverage, weighted coverage by company tier, conflict counts, room/panel utilisation, average/median/p95 student waiting time, unscheduled breakdown, replan churn, displacement minutes, and stability. Stability is defined as `1 - changed_existing_future_interviews / existing_future_interviews`.

## Replanning strategy

Replanning uses the existing schedule as the baseline. Completed interviews are never moved. Near-term future appointments are frozen unless directly invalidated. Unaffected interviews are preserved in the occupancy map before affected work is repaired. Affected interviews first try the same assignment, then nearby shifts, then later feasible slots. This avoids rebuilding everything and reduces operational confusion for students, companies, rooms, and coordinators.

## Constraint bending philosophy

Hard resource and safety constraints never bend. Business priorities are configurable through named weights in `backend/app/scheduler/policy.py`. When demand exceeds capacity, the system suggests priority-aware displacement by marking lower-feasibility items unresolved, but the coordinator retains final authority.

## Dataset realism

The generator uses branch-weighted cohorts, CGPA centered around 7-8 with a smaller high-CGPA tail, correlated shortlist probabilities, realistic company categories, tiered CGPA cutoffs, non-uniform panel counts, different durations, and high-pressure Day-1 overlaps.

## Running locally

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

Use Node 22 LTS for the smoothest local frontend install/build experience.

Docker Compose:

```bash
docker compose up --build
```

## Running tests

```bash
cd backend
python -m pytest -q
```

Frontend checks after `npm install`:

```bash
cd frontend
npm run typecheck
npm run build
```

## Live defense instructions

1. Reset demo.
2. Generate seeded dataset.
3. Generate initial schedule.
4. Open `/defense`.
5. Set simulated Day-1 time.
6. Trigger `Day-1 Crisis`.
7. Run replan.
8. Show diff, churn, notifications, and unresolved interviews.
9. Validate schedule.
10. Use the CLI backup if the browser is unavailable.

CLI backup:

```bash
cd backend
python -m app.demo_defense
```

## Tradeoffs and future improvements

The scheduler is a deterministic candidate-slot heuristic rather than a full CP-SAT implementation. `ortools` is included in requirements for future solver-backed optimization, but the current engine prioritizes demo reliability and runtime. Production improvements would include incremental CP-SAT windows, richer coordinator overrides, WebSocket event streaming, CSV/PDF exports, and normalized SQLAlchemy tables instead of snapshot persistence.
