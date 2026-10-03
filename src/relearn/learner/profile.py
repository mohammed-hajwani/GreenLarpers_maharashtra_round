from relearn.content import load_content
from relearn.learner.state import posterior_mean
from relearn.learner.store import LearnerStore


def profile_rows(store: LearnerStore, learner_id: str) -> list[dict]:
    content = load_content()
    timeline = store.timeline(learner_id)
    return [
        {
            "misconception": r.misconception,
            "label": content.misconceptions[r.misconception].label,
            "state": r.state.value,
            "posterior_held": round(posterior_mean(r), 3),
            "attempts": sum(1 for e in timeline if e["misconception"] == r.misconception and e["kind"] != "state"),
            "strategies_tried": ", ".join(r.strategies_tried),
        }
        for r in store.records(learner_id)
    ]
