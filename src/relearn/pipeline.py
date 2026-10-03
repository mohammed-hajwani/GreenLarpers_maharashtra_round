from relearn.assessment.evaluator import evaluate_assessment, passes_reassessment
from relearn.assessment.planner import plan_assessment, plan_retest
from relearn.config import load_config
from relearn.content import load_content
from relearn.diagnosis.diagnoser import diagnose
from relearn.diagnosis.disambiguator import ProbeChoice, ProbeStep, apply_probe, choose_probe
from relearn.intervention.builder import build_intervention
from relearn.intervention.checker import check_intervention
from relearn.intervention.selector import EXHAUSTED, select_strategy
from relearn.learner.state import on_assessment, on_diagnosis, on_intervention, on_retest, posterior_mean
from relearn.learner.store import LearnerStore
from relearn.llm.base import LLMClient
from relearn.llm.stub import StubLLMClient
from relearn.models.baseline import BaselineModel
from relearn.schemas import (
    AssessmentItem,
    AssessmentResult,
    Diagnosis,
    Intervention,
    LearnerRecord,
    LearnerResponse,
    MisconceptionState,
    Question,
)


class Tutor:
    def __init__(self, store: LearnerStore, model: BaselineModel | None = None, llm: LLMClient | None = None):
        self.store = store
        self.model = model
        self.llm = llm or StubLLMClient()

    def submit(self, learner_id: str, question: Question, response: LearnerResponse) -> Diagnosis:
        d = diagnose(question, response, self.model)
        self.store.log(
            learner_id,
            "practice",
            question.question_id,
            None if d.is_correct else d.top_labels[0][0],
            d.is_correct,
            {"answer": response.answer, "working": response.working, "top": d.top_labels},
        )
        return d

    def next_probe(self, diagnosis: Diagnosis, used: set[str]) -> ProbeChoice | None:
        return choose_probe(diagnosis, used)

    def answer_probe(
        self, learner_id: str, diagnosis: Diagnosis, choice: ProbeChoice, answer: str
    ) -> tuple[Diagnosis, ProbeStep]:
        updated, step = apply_probe(diagnosis, choice, answer)
        self.store.log(
            learner_id,
            "probe",
            choice.probe.probe_id,
            payload={
                "answer": answer,
                "top": updated.top_labels,
                "expected_gain": step.expected_gain,
                "entropy_before": step.entropy_before,
                "entropy_after": step.entropy_after,
                "runners_up": step.runners_up,
            },
        )
        return updated, step

    def confirm(self, learner_id: str, diagnosis: Diagnosis) -> LearnerRecord | None:
        if diagnosis.is_correct:
            return None
        label, confidence = diagnosis.top_labels[0]
        record = on_diagnosis(self.store.get(learner_id, label), confidence)
        self.store.put(record)
        self.store.log(learner_id, "state", label, label, payload={"state": record.state.value})
        return record

    def intervene(
        self, learner_id: str, misconception: str, response: LearnerResponse
    ) -> Intervention | None:
        record = self.store.get(learner_id, misconception)
        tried = list(record.strategies_tried)
        while (strategy := select_strategy(misconception, tried)) != EXHAUSTED:
            iv = build_intervention(
                misconception, strategy, response, self.store.records(learner_id), self.llm
            )
            if check_intervention(iv):
                record = on_intervention(record, strategy)
                self.store.put(record)
                self.store.bump_stat(misconception, strategy, "delivered")
                self.store.log(
                    learner_id, "intervention", strategy, misconception, payload={"state": "intervened"}
                )
                return iv
            tried.append(strategy)
        self.store.log(learner_id, "flag_for_human", misconception, misconception)
        return None

    def plan(self, learner_id: str, misconception: str) -> list[AssessmentItem]:
        return plan_assessment(misconception, self.store.seen_items(learner_id))

    def _log_items(
        self, learner_id: str, items: list[AssessmentItem], result: AssessmentResult, answers: dict
    ):
        for i in items:
            self.store.log(
                learner_id,
                i.kind,
                i.item_id,
                i.misconception,
                result.item_correct[i.item_id],
                {"answer": answers.get(i.item_id, "")},
            )

    def submit_assessment(
        self, learner_id: str, misconception: str, items: list[AssessmentItem], answers: dict[str, str]
    ) -> tuple[AssessmentResult, LearnerRecord]:
        result = evaluate_assessment(items, answers)
        self._log_items(learner_id, items, result, answers)
        record = on_assessment(self.store.get(learner_id, misconception), result)
        due = None
        if passes_reassessment(result) and record.state == MisconceptionState.intervened:
            due = self.store.attempt_count(learner_id) + load_config().assessment.retest_gap
        self.store.put(record, due)
        self.store.log(
            learner_id, "state", misconception, misconception, payload={"state": record.state.value}
        )
        return result, record

    def due_retests(self, learner_id: str) -> list[tuple[str, AssessmentItem]]:
        count = self.store.attempt_count(learner_id)
        out = []
        for record in self.store.records(learner_id):
            due = self.store.retest_due(learner_id, record.misconception)
            if record.state == MisconceptionState.intervened and due is not None and count >= due:
                out.append(
                    (
                        record.misconception,
                        plan_retest(record.misconception, self.store.seen_items(learner_id)),
                    )
                )
        return out

    def pending_retest(self, learner_id: str, misconception: str) -> int | None:
        due = self.store.retest_due(learner_id, misconception)
        if due is None:
            return None
        return max(due - self.store.attempt_count(learner_id), 0)

    def submit_retest(
        self, learner_id: str, item: AssessmentItem, answer: str
    ) -> tuple[AssessmentResult, LearnerRecord]:
        answers = {item.item_id: answer}
        result = evaluate_assessment([item], answers)
        self._log_items(learner_id, [item], result, answers)
        before = self.store.get(learner_id, item.misconception)
        record = on_retest(before, result)
        if record.state == MisconceptionState.resolved and record.strategies_tried:
            self.store.bump_stat(item.misconception, record.strategies_tried[-1], "resolved")
        self.store.put(record, None)
        self.store.log(
            learner_id, "state", item.misconception, item.misconception, payload={"state": record.state.value}
        )
        return result, record

    def update_learner(self, learner_id: str, misconception: str, result: AssessmentResult) -> LearnerRecord:
        record = self.store.get(learner_id, misconception)
        record = (
            on_retest(record, result) if result.retest_passed is not None else on_assessment(record, result)
        )
        self.store.put(record)
        return record

    def profile(self, learner_id: str) -> list[dict]:
        content = load_content()
        timeline = self.store.timeline(learner_id)
        rows = []
        for r in self.store.records(learner_id):
            rows.append(
                {
                    "misconception": r.misconception,
                    "label": content.misconceptions[r.misconception].label,
                    "state": r.state.value,
                    "posterior_held": round(posterior_mean(r), 3),
                    "attempts": sum(
                        1 for e in timeline if e["misconception"] == r.misconception and e["kind"] != "state"
                    ),
                    "strategies_tried": ", ".join(r.strategies_tried),
                }
            )
        return rows
