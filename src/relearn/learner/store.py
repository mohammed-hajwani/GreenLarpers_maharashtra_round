import json
import sqlite3
import threading
from pathlib import Path

from relearn.learner.state import new_record, now
from relearn.schemas import LearnerRecord

SCHEMA = [
    (
        "CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "learner_id TEXT NOT NULL, "
        "ts TEXT NOT NULL, kind TEXT NOT NULL, ref_id TEXT NOT NULL, misconception TEXT, correct INTEGER, "
        "payload TEXT NOT NULL)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS learner_state (learner_id TEXT NOT NULL, misconception TEXT NOT NULL, "
        "record TEXT NOT NULL, retest_due INTEGER, PRIMARY KEY (learner_id, misconception))"
    ),
    (
        "CREATE TABLE IF NOT EXISTS intervention_stats (misconception TEXT NOT NULL, strategy TEXT NOT NULL, "
        "delivered INTEGER NOT NULL DEFAULT 0, resolved INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY (misconception, strategy))"
    ),
    "CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
]

COUNTED_KINDS = ("practice", "transfer", "trap", "retest")


class LearnerStore:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        for statement in SCHEMA:
            self.conn.execute(statement)
        self.conn.commit()

    def log(
        self,
        learner_id: str,
        kind: str,
        ref_id: str,
        misconception: str | None = None,
        correct: bool | None = None,
        payload: dict | None = None,
    ) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO attempts (learner_id, ts, kind, ref_id, misconception, correct, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    learner_id,
                    now(),
                    kind,
                    ref_id,
                    misconception,
                    None if correct is None else int(correct),
                    json.dumps(payload or {}),
                ),
            )
            self.conn.commit()

    def attempt_count(self, learner_id: str) -> int:
        marks = ",".join("?" * len(COUNTED_KINDS))
        row = self.conn.execute(
            f"SELECT COUNT(*) FROM attempts WHERE learner_id = ? AND kind IN ({marks})",
            (learner_id, *COUNTED_KINDS),
        ).fetchone()
        return int(row[0])

    def seen_items(self, learner_id: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT ref_id FROM attempts WHERE learner_id = ? AND kind IN ('transfer', 'trap', 'retest')",
            (learner_id,),
        ).fetchall()
        return {r[0] for r in rows}

    def timeline(self, learner_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT ts, kind, ref_id, misconception, correct, payload FROM attempts "
            "WHERE learner_id = ? ORDER BY id",
            (learner_id,),
        ).fetchall()
        return [
            {
                "ts": r[0],
                "kind": r[1],
                "ref_id": r[2],
                "misconception": r[3],
                "correct": None if r[4] is None else bool(r[4]),
                **json.loads(r[5]),
            }
            for r in rows
        ]

    def get(self, learner_id: str, misconception: str) -> LearnerRecord:
        row = self.conn.execute(
            "SELECT record FROM learner_state WHERE learner_id = ? AND misconception = ?",
            (learner_id, misconception),
        ).fetchone()
        return LearnerRecord.model_validate_json(row[0]) if row else new_record(learner_id, misconception)

    def put(self, record: LearnerRecord, retest_due: int | None = None) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO learner_state (learner_id, misconception, record, retest_due) "
                "VALUES (?, ?, ?, ?)",
                (record.learner_id, record.misconception, record.model_dump_json(), retest_due),
            )
            self.conn.commit()

    def retest_due(self, learner_id: str, misconception: str) -> int | None:
        row = self.conn.execute(
            "SELECT retest_due FROM learner_state WHERE learner_id = ? AND misconception = ?",
            (learner_id, misconception),
        ).fetchone()
        return row[0] if row else None

    def records(self, learner_id: str) -> list[LearnerRecord]:
        rows = self.conn.execute(
            "SELECT record FROM learner_state WHERE learner_id = ? ORDER BY misconception", (learner_id,)
        ).fetchall()
        return [LearnerRecord.model_validate_json(r[0]) for r in rows]

    def bump_stat(self, misconception: str, strategy: str, column: str) -> None:
        if column not in ("delivered", "resolved"):
            raise ValueError(column)
        with self.lock:
            self.conn.execute(
                "INSERT OR IGNORE INTO intervention_stats (misconception, strategy) VALUES (?, ?)",
                (misconception, strategy),
            )
            self.conn.execute(
                f"UPDATE intervention_stats SET {column} = {column} + 1 "
                "WHERE misconception = ? AND strategy = ?",
                (misconception, strategy),
            )
            self.conn.commit()

    def reset(self, learner_id: str) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM attempts WHERE learner_id = ?", (learner_id,))
            self.conn.execute("DELETE FROM learner_state WHERE learner_id = ?", (learner_id,))
            self.conn.commit()
