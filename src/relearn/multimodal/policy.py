from relearn.learner.store import LearnerStore
from relearn.multimodal.modality import choose_modality

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS modality_stats (misconception TEXT NOT NULL, modality TEXT NOT NULL, "
    "delivered INTEGER NOT NULL DEFAULT 0, success INTEGER NOT NULL DEFAULT 0, failure INTEGER NOT NULL DEFAULT 0, "
    "PRIMARY KEY (misconception, modality))"
)


def _ensure(store: LearnerStore) -> None:
    with store.lock:
        store.conn.execute(SCHEMA)
        store.conn.commit()


def modality_stats(store: LearnerStore, misconception: str | None = None) -> dict:
    _ensure(store)
    query = "SELECT misconception, modality, delivered, success, failure FROM modality_stats"
    rows = store.conn.execute(query).fetchall()
    out: dict = {}
    for m, mod, delivered, success, failure in rows:
        if misconception is None or m == misconception:
            out.setdefault(m, {})[mod] = {"delivered": delivered, "success": success, "failure": failure}
    return out if misconception is None else out.get(misconception, {})


def _bump(store: LearnerStore, misconception: str, modality: str, column: str) -> None:
    _ensure(store)
    with store.lock:
        store.conn.execute(
            "INSERT OR IGNORE INTO modality_stats (misconception, modality) VALUES (?, ?)", (misconception, modality)
        )
        store.conn.execute(
            f"UPDATE modality_stats SET {column} = {column} + 1 WHERE misconception = ? AND modality = ?",
            (misconception, modality),
        )
        store.conn.commit()


def tried_modalities(store: LearnerStore, learner_id: str, misconception: str) -> list[str]:
    return [
        e.get("modality", "text")
        for e in store.timeline(learner_id)
        if e["kind"] == "intervention" and e["misconception"] == misconception
    ]


def pick_for(store: LearnerStore, learner_id: str, misconception: str) -> tuple[str, dict]:
    stats = {mod: (s["success"], s["failure"]) for mod, s in modality_stats(store, misconception).items()}
    tried = tried_modalities(store, learner_id, misconception)
    modality, draws = choose_modality(misconception, stats, tried, f"{learner_id}|{misconception}|{len(tried)}")
    _bump(store, misconception, modality, "delivered")
    return modality, {"draws": draws, "tried_before": tried}


def record_outcome(store: LearnerStore, learner_id: str, misconception: str, passed: bool) -> str | None:
    tried = tried_modalities(store, learner_id, misconception)
    if not tried:
        return None
    _bump(store, misconception, tried[-1], "success" if passed else "failure")
    return tried[-1]


def intervention_payload(mode: str, modality: str, why: dict, passages: list[dict]) -> dict:
    return {
        "state": "intervened",
        "mode": mode,
        "modality": modality,
        "modality_draws": why["draws"],
        "sources": [p["passage_id"] for p in passages],
    }
