from relearn.content import load_content
from relearn.learner.store import LearnerStore
from relearn.progress.simulator import features


def concept_events(store: LearnerStore, learner_id: str, concept: str) -> list[dict]:
    events = []
    for h in store.mastery_history(learner_id):
        if h["concept"] != concept:
            continue
        detail = h["detail"]
        if h["event"] == "practice":
            events.append(
                {
                    "kind": "practice",
                    "correct": bool(detail.get("correct")),
                    "difficulty": detail.get("difficulty", "medium"),
                    "confidence": None if detail.get("correct") else detail.get("confidence", 0.0),
                    "mastery_after": h["after"],
                }
            )
        elif h["event"] == "probe":
            consistent = detail.get("probe_signal") == "consistent_with_misconception"
            events.append({"kind": "probe", "consistent": consistent, "mastery_after": h["after"]})
        elif h["event"] in ("transfer", "trap"):
            events.append({"kind": h["event"], "correct": bool(detail.get("correct")), "mastery_after": h["after"]})
    members = set(load_content().concepts[concept].misconceptions)
    interventions = [
        e for e in store.timeline(learner_id) if e["kind"] == "intervention" and e["misconception"] in members
    ]
    events.extend({"kind": "intervention"} for _ in interventions)
    return events


def learner_features(store: LearnerStore, learner_id: str, concept: str) -> dict[str, float] | None:
    events = concept_events(store, learner_id, concept)
    if not any(e["kind"] == "practice" for e in events):
        return None
    return features(events)
