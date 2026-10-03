import json
import sqlite3
import threading
from pathlib import Path

from relearn.learner.mastery import MasteryState, MasteryUpdate, prior
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
    (
        "CREATE TABLE IF NOT EXISTS concept_mastery (learner_id TEXT NOT NULL, concept TEXT NOT NULL, "
        "alpha REAL NOT NULL, beta REAL NOT NULL, updated TEXT NOT NULL, PRIMARY KEY (learner_id, concept))"
    ),
    (
        "CREATE TABLE IF NOT EXISTS mastery_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "learner_id TEXT NOT NULL, "
        "ts TEXT NOT NULL, concept TEXT NOT NULL, event TEXT NOT NULL, ref_id TEXT NOT NULL, "
        "before REAL NOT NULL, after REAL NOT NULL, alpha_before REAL NOT NULL, beta_before REAL NOT NULL, "
        "alpha_after REAL NOT NULL, beta_after REAL NOT NULL, detail TEXT NOT NULL)"
    ),
]

TRACE_TABLE = (
    "CREATE TABLE IF NOT EXISTS decision_trace (id INTEGER PRIMARY KEY AUTOINCREMENT, learner_id TEXT NOT NULL, "
    "ts TEXT NOT NULL, kind TEXT NOT NULL, input_hash TEXT NOT NULL, record TEXT NOT NULL)"
)
COUNTED_KINDS = ("practice", "transfer", "trap", "retest")


class LearnerStore:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        for statement in [*SCHEMA, TRACE_TABLE]:
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
            "SELECT ts, kind, ref_id, misconception, correct, payload FROM attempts WHERE learner_id = ? ORDER BY id",
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
                f"UPDATE intervention_stats SET {column} = {column} + 1 WHERE misconception = ? AND strategy = ?",
                (misconception, strategy),
            )
            self.conn.commit()

    def mastery(self, learner_id: str, concept: str) -> MasteryState:
        row = self.conn.execute(
            "SELECT alpha, beta FROM concept_mastery WHERE learner_id = ? AND concept = ?",
            (learner_id, concept),
        ).fetchone()
        return MasteryState(row[0], row[1]) if row else prior()

    def all_mastery(self, learner_id: str) -> dict[str, MasteryState]:
        rows = self.conn.execute(
            "SELECT concept, alpha, beta FROM concept_mastery WHERE learner_id = ?", (learner_id,)
        ).fetchall()
        return {r[0]: MasteryState(r[1], r[2]) for r in rows}

    def save_mastery(self, learner_id: str, state: MasteryState, record: MasteryUpdate) -> int:
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO concept_mastery (learner_id, concept, alpha, beta, updated) "
                "VALUES (?, ?, ?, ?, ?)",
                (learner_id, record.concept, state.alpha, state.beta, now()),
            )
            cursor = self.conn.execute(
                "INSERT INTO mastery_log (learner_id, ts, concept, event, ref_id, before, after, "
                "alpha_before, "
                "beta_before, alpha_after, beta_after, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    learner_id,
                    now(),
                    record.concept,
                    record.event,
                    record.ref_id,
                    record.before,
                    record.after,
                    record.alpha_before,
                    record.beta_before,
                    record.alpha_after,
                    record.beta_after,
                    json.dumps(record.detail),
                ),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    def mastery_history(self, learner_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, ts, concept, event, ref_id, before, after, alpha_before, beta_before, alpha_after, "
            "beta_after, detail FROM mastery_log WHERE learner_id = ? ORDER BY id",
            (learner_id,),
        ).fetchall()
        keys = [
            "id",
            "ts",
            "concept",
            "event",
            "ref_id",
            "before",
            "after",
            "alpha_before",
            "beta_before",
            "alpha_after",
            "beta_after",
        ]
        return [{**dict(zip(keys, r[:11], strict=True)), "detail": json.loads(r[11])} for r in rows]

    def save_trace(self, learner_id: str, kind: str, input_hash: str, record: dict) -> int:
        with self.lock:
            cursor = self.conn.execute(
                "INSERT INTO decision_trace (learner_id, ts, kind, input_hash, record) VALUES (?, ?, ?, ?, ?)",
                (learner_id, now(), kind, input_hash, json.dumps(record)),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    def trace(self, trace_id: int) -> dict:
        row = self.conn.execute(
            "SELECT id, ts, kind, input_hash, record FROM decision_trace WHERE id = ?", (trace_id,)
        ).fetchone()
        return {"id": row[0], "ts": row[1], "kind": row[2], "input_hash": row[3], **json.loads(row[4])}

    def traces(self, learner_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id FROM decision_trace WHERE learner_id = ? ORDER BY id", (learner_id,)
        ).fetchall()
        return [self.trace(r[0]) for r in rows]

    def reset(self, learner_id: str) -> None:
        with self.lock:
            for table in ("attempts", "learner_state", "concept_mastery", "mastery_log", "decision_trace"):
                self.conn.execute(f"DELETE FROM {table} WHERE learner_id = ?", (learner_id,))
            self.conn.commit()
