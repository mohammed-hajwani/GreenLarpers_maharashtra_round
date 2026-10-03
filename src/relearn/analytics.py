import json
from collections import Counter
from pathlib import Path

from relearn.adaptive.difficulty import BAND_LEVELS
from relearn.config import load_config
from relearn.content import load_content
from relearn.learner.store import LearnerStore
from relearn.models.registry import BASELINE, EMBEDDING, read_metadata
from relearn.progress.features import learner_features
from relearn.progress.model import LABEL, predict


def dashboard_data(store: LearnerStore, learner_id: str) -> dict:
    content = load_content()
    mastery = store.all_mastery(learner_id)
    history = store.mastery_history(learner_id)
    timeline = store.timeline(learner_id)
    traces = store.traces(learner_id)
    practice = [e for e in timeline if e["kind"] == "practice"]
    practice_traces = [t for t in traces if t["kind"] == "practice"]
    probes = [p for t in practice_traces for p in t["probes"]]
    assessments = [t for t in traces if t["kind"] in ("assessment", "retest") and t["mastery_updates"]]
    return {
        "empty": not practice and not history,
        "overall_mastery": sum(m.mean for m in mastery.values()) / len(mastery) if mastery else None,
        "concept_mastery": [
            {"concept": content.concepts[c].name, "mastery": m.mean, "evidence": m.alpha + m.beta - 2}
            for c, m in mastery.items()
        ],
        "mastery_over_time": [
            {"step": i + 1, "concept": content.concepts[h["concept"]].name, "mastery": h["after"], "event": h["event"]}
            for i, h in enumerate(history)
        ],
        "misconception_distribution": dict(
            Counter(e["misconception"] for e in practice if e["misconception"] and e["correct"] is False)
        ),
        "average_confidence": (
            sum(t["final"]["confidence"] for t in practice_traces) / len(practice_traces) if practice_traces else None
        ),
        "probe_effectiveness": [
            {
                "probe": p["probe_id"],
                "entropy_before": p["entropy_before"],
                "entropy_after": p["entropy_after"],
                "confidence_before": p["confidence_before"],
                "confidence_after": p["confidence_after"],
            }
            for p in probes
        ],
        "intervention_effectiveness": [
            {
                "trace": t["id"],
                "misconception": t["misconception"],
                "kind": t["kind"],
                "mastery_before": t["mastery_updates"][0]["before"],
                "mastery_after": t["mastery_updates"][-1]["after"],
                "state_after": t["state_after"],
            }
            for t in assessments
        ],
        "progress_estimates": progress_estimates(store, learner_id, list(mastery)),
        "progress_label": LABEL,
        "difficulty_progression": [
            {"attempt": i + 1, "difficulty": e["difficulty"], "level": BAND_LEVELS.get(e["difficulty"], 0)}
            for i, e in enumerate(e for e in practice if e.get("difficulty"))
        ],
    }


def progress_estimates(store: LearnerStore, learner_id: str, concepts: list[str]) -> list[dict]:
    content = load_content()
    rows = []
    for concept in concepts:
        feats = learner_features(store, learner_id, concept)
        estimate = predict(feats) if feats else None
        if estimate:
            rows.append(
                {
                    "concept": content.concepts[concept].name,
                    "p_reach_mastery": estimate["reach_mastery"],
                    "p_misconception_persists": estimate["misconception_persists"],
                    "practice_attempts": int(feats["attempts"]),
                }
            )
    return rows


def evaluation_data(metrics_path: Path | None = None) -> dict:
    path = metrics_path or load_config().path("reports_dir") / "metrics.json"
    if not path.exists():
        return {"available": False}
    metrics = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "metrics": metrics,
        "metadata": {kind: read_metadata(kind) for kind in (BASELINE, EMBEDDING)},
    }
