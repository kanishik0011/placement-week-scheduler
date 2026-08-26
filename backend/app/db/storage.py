from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.generator import generate_dataset
from app.models import Dataset


class StateStore:
    """SQLite-backed snapshot store.

    SQLAlchemy is listed in project requirements for production-style evolution;
    this stdlib store keeps the demo resilient if dependency installation is not
    available during review.
    """

    def __init__(self, path: str | Path = "placement_scheduler.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with self._conn() as conn:
            conn.execute("create table if not exists state (id integer primary key check (id=1), payload text not null)")
            conn.execute("create table if not exists replans (id integer primary key autoincrement, payload text not null)")

    def load(self) -> Dataset:
        with self._conn() as conn:
            row = conn.execute("select payload from state where id=1").fetchone()
        if not row:
            dataset = generate_dataset()
            self.save(dataset)
            return dataset
        return Dataset.from_dict(json.loads(row[0]))

    def save(self, dataset: Dataset) -> None:
        payload = json.dumps(dataset.to_dict())
        with self._conn() as conn:
            conn.execute("insert or replace into state (id, payload) values (1, ?)", (payload,))

    def save_replan(self, result: dict) -> int:
        with self._conn() as conn:
            cursor = conn.execute("insert into replans (payload) values (?)", (json.dumps(result),))
            return int(cursor.lastrowid)

    def load_replan(self, replan_id: int) -> dict:
        with self._conn() as conn:
            row = conn.execute("select payload from replans where id=?", (replan_id,)).fetchone()
        if not row:
            raise KeyError(replan_id)
        return json.loads(row[0])

