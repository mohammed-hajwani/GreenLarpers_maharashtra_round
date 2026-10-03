from relearn.adaptive.difficulty import DifficultyDecision
from relearn.analytics import dashboard_data, evaluation_data
from relearn.config import load_config
from relearn.diagnosis.diagnoser import diagnose as model_diagnose
from relearn.diagnosis.disambiguator import ProbeChoice, ProbeStep
from relearn.diagnosis.explain import explain
from relearn.diagnosis.screening import has_answer_key, screen_response
from relearn.learner.store import LearnerStore
from relearn.llm.anthropic_client import make_llm
from relearn.models.loader import ActiveModel, get_active_model
from relearn.pipeline import Tutor
from relearn.progress.features import learner_features
from relearn.progress.model import predict as progress_predict
from relearn.schemas import (
    AssessmentItem,
    AssessmentResult,
    Diagnosis,
    Intervention,
    LearnerRecord,
    LearnerResponse,
    Question,
)


def create_tutor(db_path: str | None = None) -> Tutor:
    path = db_path or load_config().db_path()
    return Tutor(LearnerStore(path), get_active_model().model, make_llm())


def screen(question: Question, response: LearnerResponse) -> str | None:
    return screen_response(question, response)


def has_key(question: Question) -> bool:
    return has_answer_key(question)


def active_model() -> ActiveModel:
    return get_active_model()


def predict(question: Question, response: LearnerResponse) -> Diagnosis:
    return model_diagnose(question, response, get_active_model().model)


def explain_prediction(question: Question, response: LearnerResponse, label: str) -> dict:
    model = get_active_model().model
    return explain(model, question, response, label) if model else {}


def diagnose(tutor: Tutor, learner_id: str, question: Question, response: LearnerResponse) -> Diagnosis:
    return tutor.submit(learner_id, question, response)


def next_probe(tutor: Tutor, diagnosis: Diagnosis, used: set[str]) -> ProbeChoice | None:
    return tutor.next_probe(diagnosis, used)


def answer_probe(
    tutor: Tutor, learner_id: str, diagnosis: Diagnosis, choice: ProbeChoice, answer: str
) -> tuple[Diagnosis, ProbeStep]:
    return tutor.answer_probe(learner_id, diagnosis, choice, answer)


def finalize(
    tutor: Tutor,
    learner_id: str,
    question: Question,
    response: LearnerResponse,
    initial: Diagnosis,
    final: Diagnosis,
    steps: list[ProbeStep],
) -> dict:
    return tutor.finalize_interaction(learner_id, question, response, initial, final, steps)


def intervention(tutor: Tutor, learner_id: str, misconception: str, response: LearnerResponse) -> Intervention | None:
    return tutor.intervene(learner_id, misconception, response)


def plan_assessment(tutor: Tutor, learner_id: str, misconception: str) -> list[AssessmentItem]:
    return tutor.plan(learner_id, misconception)


def submit_assessment(
    tutor: Tutor, learner_id: str, misconception: str, items: list[AssessmentItem], answers: dict[str, str]
) -> tuple[AssessmentResult, LearnerRecord]:
    return tutor.submit_assessment(learner_id, misconception, items, answers)


def due_retests(tutor: Tutor, learner_id: str) -> list[tuple[str, AssessmentItem]]:
    return tutor.due_retests(learner_id)


def pending_retest(tutor: Tutor, learner_id: str, misconception: str) -> int | None:
    return tutor.pending_retest(learner_id, misconception)


def submit_retest(
    tutor: Tutor, learner_id: str, item: AssessmentItem, answer: str
) -> tuple[AssessmentResult, LearnerRecord]:
    return tutor.submit_retest(learner_id, item, answer)


def next_question(tutor: Tutor, learner_id: str, concept: str | None = None) -> tuple[Question, DifficultyDecision]:
    return tutor.next_question(learner_id, concept)


def mastery(tutor: Tutor, learner_id: str) -> dict[str, float]:
    return {c: m.mean for c, m in tutor.store.all_mastery(learner_id).items()}


def progress(tutor: Tutor, learner_id: str, concept: str) -> dict | None:
    feats = learner_features(tutor.store, learner_id, concept)
    return progress_predict(feats) if feats else None


def profile(tutor: Tutor, learner_id: str) -> list[dict]:
    return tutor.profile(learner_id)


def timeline(tutor: Tutor, learner_id: str) -> list[dict]:
    return tutor.store.timeline(learner_id)


def trace(tutor: Tutor, trace_id: int) -> dict:
    return tutor.store.trace(trace_id)


def traces(tutor: Tutor, learner_id: str) -> list[dict]:
    return tutor.store.traces(learner_id)


def passages_by_id() -> dict[str, str]:
    from relearn.rag.retriever import build_corpus

    return {p.passage_id: p.text for p in build_corpus()}


def log_event(tutor: Tutor, learner_id: str, kind: str, ref_id: str, misconception: str | None, payload: dict) -> None:
    tutor.store.log(learner_id, kind, ref_id, misconception, None, payload)


def misconception_states(tutor: Tutor, learner_id: str) -> dict[str, str]:
    return {r.misconception: r.state.value for r in tutor.store.records(learner_id)}


def concept_status(tutor: Tutor, learner_id: str, concept: str) -> str:
    from relearn.content import load_content

    members = load_content().concepts[concept].misconceptions
    states = {m: s for m, s in misconception_states(tutor, learner_id).items() if m in members}
    stored = tutor.store.all_mastery(learner_id).get(concept)
    if stored is None and not states:
        return "not_started"
    flagged = any(e["kind"] == "review_flag" and e["ref_id"] == concept for e in tutor.store.timeline(learner_id))
    mastered = stored is not None and stored.mean >= load_config().difficulty.hard_above
    if mastered and all(s == "resolved" for s in states.values()):
        return "mastered"
    return "review" if flagged else "in_progress"


def diagram(misconception: str) -> str | None:
    from relearn.multimodal.diagrams import diagram_svg

    return diagram_svg(misconception)


def diagram_text(misconception: str) -> tuple[str, str]:
    from relearn.multimodal.diagrams import diagram_caption

    return diagram_caption(misconception)


def simulation(misconception: str) -> str | None:
    from relearn.multimodal.simulations import simulation_html

    return simulation_html(misconception)


def simulation_caption(misconception: str) -> str:
    from relearn.multimodal.simulations import simulation_spec

    spec = simulation_spec(misconception)
    return spec["caption"] if spec else ""


def modality_stats(tutor: Tutor) -> dict:
    from relearn.multimodal.policy import modality_stats as stats

    return stats(tutor.store)


def review_queue(tutor: Tutor) -> list[dict]:
    return tutor.store.review_queue()


def explain_prompt(misconception: str) -> str:
    from relearn.content import load_content

    return load_content().misconceptions[misconception].explain_prompt


def check_explanation(tutor: Tutor, learner_id: str, misconception: str, text: str) -> tuple[str, float]:
    from relearn.content import load_content
    from relearn.learner.mastery import update
    from relearn.learning.explain import score_explanation

    status, prob = score_explanation(tutor.model, misconception, text)
    if status == "needs_more":
        return status, prob
    tutor.store.log(
        learner_id,
        "explain_back",
        misconception,
        misconception,
        status == "clear",
        {"status": status, "probability": prob, "text": text},
    )
    m = load_config().mastery
    evidence = {"clear": (m.transfer_correct, 0.0), "tricky": (0.0, m.transfer_wrong)}.get(status, (0.0, 0.0))
    concept = load_content().concept_of(misconception)
    if concept:
        state, record = update(
            tutor.store.mastery(learner_id, concept),
            concept,
            "explain_back",
            misconception,
            (*evidence, {"status": status, "probability": prob}),
        )
        tutor.store.save_mastery(learner_id, state, record)
    return status, prob


def reset(tutor: Tutor, learner_id: str) -> None:
    tutor.store.reset(learner_id)


def dashboard(tutor: Tutor, learner_id: str) -> dict:
    return dashboard_data(tutor.store, learner_id)


def evaluate() -> dict:
    return evaluation_data()
