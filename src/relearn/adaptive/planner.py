from relearn.adaptive.difficulty import DifficultyDecision, decide_band, instantiate, pick_template
from relearn.content import load_content
from relearn.learner.store import LearnerStore
from relearn.schemas import Question

ACTIVE = ("active", "intervened", "relapsed")


def concept_history(store: LearnerStore, learner_id: str, concept: str) -> list[dict]:
    return [e for e in store.timeline(learner_id) if e["kind"] == "practice" and e.get("concept") == concept]


def target_concept(store: LearnerStore, learner_id: str) -> str:
    content = load_content()
    mastery = store.all_mastery(learner_id)
    states = {r.misconception: r.state.value for r in store.records(learner_id)}
    active = [c.id for c in content.concepts.values() if any(states.get(m) in ACTIVE for m in c.misconceptions)]
    pool = active or list(content.concepts)
    order = list(content.concepts)
    return min(pool, key=lambda c: (mastery[c].mean if c in mastery else 0.5, order.index(c)))


def plan_next_question(
    store: LearnerStore, learner_id: str, concept: str | None = None
) -> tuple[Question, DifficultyDecision]:
    content = load_content()
    concept = concept or target_concept(store, learner_id)
    mastery = store.mastery(learner_id, concept).mean
    history = concept_history(store, learner_id, concept)
    states = {
        r.misconception: r.state.value
        for r in store.records(learner_id)
        if r.misconception in content.concepts[concept].misconceptions
    }
    previous = history[-1].get("difficulty") if history else None
    base, band, reasons, factors = decide_band(mastery, history, states, previous)
    template, gap = pick_template(concept, band, [h.get("template_id", "") for h in history])
    decision = DifficultyDecision(
        concept=concept,
        concept_name=content.concepts[concept].name,
        mastery=mastery,
        base_band=base,
        band=band,
        reasons=reasons + ([gap] if gap else []),
        factors=factors,
        template_id=template.template_id,
        coverage_gap=gap,
    )
    return instantiate(template, store.attempt_count(learner_id)), decision
