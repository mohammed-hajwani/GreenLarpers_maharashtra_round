from relearn.adaptive.difficulty import DifficultyDecision
from relearn.adaptive.planner import concept_history, plan_next_question, target_concept
from relearn.assessment.evaluator import evaluate_assessment, passes_reassessment
from relearn.assessment.planner import plan_assessment, plan_retest
from relearn.config import load_config
from relearn.content import load_content
from relearn.diagnosis.diagnoser import diagnose
from relearn.diagnosis.disambiguator import ProbeChoice, ProbeStep, apply_probe, choose_probe
from relearn.diagnosis.explain import explain
from relearn.diagnosis.routing import thresholds_for
from relearn.intervention.checker import check_intervention
from relearn.intervention.grounded import build_grounded_intervention
from relearn.intervention.selector import EXHAUSTED, select_strategy
from relearn.learner.mastery import MasteryUpdate, item_evidence, practice_evidence, probe_evidence, update
from relearn.learner.profile import profile_rows
from relearn.learner.state import on_assessment, on_diagnosis, on_intervention, on_retest
from relearn.learner.store import LearnerStore
from relearn.llm.base import LLMClient
from relearn.llm.stub import StubLLMClient
from relearn.models.base import TextClassifier
from relearn.rag.retriever import retrieve_for
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
from relearn.trace import assessment_trace, practice_trace


class Tutor:
    def __init__(self, store: LearnerStore, model: TextClassifier | None = None, llm: LLMClient | None = None):
        self.store = store
        self.model = model
        self.llm = llm or StubLLMClient()
        self.retriever = None
        self.last_trace: dict | None = None

    def submit(self, learner_id: str, question: Question, response: LearnerResponse) -> Diagnosis:
        d = diagnose(question, response, self.model)
        self.store.log(
            learner_id,
            "practice",
            question.question_id,
            d.misconception,
            d.is_correct,
            {
                "answer": response.answer,
                "working": response.working,
                "top": d.top_labels,
                "confidence": d.confidence,
                "route": d.route,
                "template_id": question.template_id,
                "concept": self.question_concept(question, d),
                "difficulty": self.question_difficulty(question),
            },
        )
        return d

    def _mastery(
        self, learner_id: str, concept: str | None, event: str, ref_id: str, evidence: tuple
    ) -> MasteryUpdate | None:
        if concept is None:
            return None
        state, record = update(self.store.mastery(learner_id, concept), concept, event, ref_id, evidence)
        record.detail["log_id"] = self.store.save_mastery(learner_id, state, record)
        return record

    def question_concept(self, question: Question, diagnosis: Diagnosis) -> str | None:
        content = load_content()
        concept = content.concept_of_template(question.template_id)
        if concept is None and not diagnosis.is_correct:
            concept = content.concept_of(diagnosis.misconception)
        return concept

    def question_difficulty(self, question: Question) -> str:
        t = next((t for t in load_content().templates if t.template_id == question.template_id), None)
        return t.difficulty if t else "medium"

    def next_probe(self, diagnosis: Diagnosis, used: set[str]) -> ProbeChoice | None:
        return choose_probe(diagnosis, used)

    def answer_probe(
        self, learner_id: str, diagnosis: Diagnosis, choice: ProbeChoice, answer: str
    ) -> tuple[Diagnosis, ProbeStep]:
        updated, step = apply_probe(diagnosis, choice, answer)
        top = diagnosis.misconception or diagnosis.top_labels[0][0]
        expected = choice.probe.expected_answer_by_label
        step_mastery = self._mastery(
            learner_id,
            load_content().concept_of(top),
            "probe",
            choice.probe.probe_id,
            probe_evidence(answer == expected.get(top), answer == expected.get("none")),
        )
        step.mastery = step_mastery
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

    def confirm(
        self, learner_id: str, diagnosis: Diagnosis, question: Question | None = None
    ) -> tuple[LearnerRecord | None, MasteryUpdate | None]:
        mastery = None
        if question is not None:
            mastery = self._mastery(
                learner_id,
                self.question_concept(question, diagnosis),
                "practice",
                question.question_id,
                practice_evidence(diagnosis.is_correct, self.question_difficulty(question), diagnosis),
            )
        if diagnosis.is_correct:
            return None, mastery
        label, confidence = diagnosis.misconception, diagnosis.misconception_confidence
        if label is None:
            return None, mastery
        record = on_diagnosis(self.store.get(learner_id, label), confidence)
        self.store.put(record)
        self.store.log(learner_id, "state", label, label, payload={"state": record.state.value})
        return record, mastery

    def intervene(self, learner_id: str, misconception: str, response: LearnerResponse) -> Intervention | None:
        record = self.store.get(learner_id, misconception)
        tried = list(record.strategies_tried)
        while (strategy := select_strategy(misconception, tried)) != EXHAUSTED:
            passages = self.retrieve(misconception, response)
            concept = load_content().concept_of(misconception)
            mastery = self.store.mastery(learner_id, concept).mean if concept else None
            iv, mode = build_grounded_intervention(misconception, strategy, response, self.llm, passages, mastery)
            iv = iv.model_copy(update={"mode": mode, "sources": passages})
            if check_intervention(iv):
                record = on_intervention(record, strategy)
                self.store.put(record)
                self.store.bump_stat(misconception, strategy, "delivered")
                self.store.log(
                    learner_id,
                    "intervention",
                    strategy,
                    misconception,
                    payload={"state": "intervened", "mode": mode, "sources": [p["passage_id"] for p in passages]},
                )
                return iv
            tried.append(strategy)
        self.store.log(learner_id, "flag_for_human", misconception, misconception)
        return None

    def retrieve(self, misconception: str, response: LearnerResponse) -> list[dict]:
        return retrieve_for(misconception, response, self.retriever)

    def plan(self, learner_id: str, misconception: str) -> list[AssessmentItem]:
        return plan_assessment(misconception, self.store.seen_items(learner_id))

    def _log_items(
        self, learner_id: str, items: list[AssessmentItem], result: AssessmentResult, answers: dict
    ) -> list[MasteryUpdate]:
        updates = []
        for i in items:
            m = self._mastery(
                learner_id,
                load_content().concept_of(i.misconception),
                i.kind,
                i.item_id,
                item_evidence(i.kind, result.item_correct[i.item_id]),
            )
            if m is not None:
                updates.append(m)
            self.store.log(
                learner_id,
                i.kind,
                i.item_id,
                i.misconception,
                result.item_correct[i.item_id],
                {"answer": answers.get(i.item_id, "")},
            )
        return updates

    def submit_assessment(
        self, learner_id: str, misconception: str, items: list[AssessmentItem], answers: dict[str, str]
    ) -> tuple[AssessmentResult, LearnerRecord]:
        result = evaluate_assessment(items, answers)
        updates = self._log_items(learner_id, items, result, answers)
        before = self.store.get(learner_id, misconception)
        record = on_assessment(before, result)
        due = None
        if passes_reassessment(result) and record.state == MisconceptionState.intervened:
            due = self.store.attempt_count(learner_id) + load_config().assessment.retest_gap
        self.store.put(record, due)
        self.store.log(learner_id, "state", misconception, misconception, payload={"state": record.state.value})
        self.last_trace = self._assessment_trace(
            learner_id, "assessment", misconception, before, record, result, updates
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
        updates = self._log_items(learner_id, [item], result, answers)
        before = self.store.get(learner_id, item.misconception)
        record = on_retest(before, result)
        if record.state == MisconceptionState.resolved and record.strategies_tried:
            self.store.bump_stat(item.misconception, record.strategies_tried[-1], "resolved")
        self.store.put(record, None)
        self.store.log(
            learner_id, "state", item.misconception, item.misconception, payload={"state": record.state.value}
        )
        self.last_trace = self._assessment_trace(
            learner_id, "retest", item.misconception, before, record, result, updates
        )
        return result, record

    def update_learner(self, learner_id: str, misconception: str, result: AssessmentResult) -> LearnerRecord:
        record = self.store.get(learner_id, misconception)
        record = on_retest(record, result) if result.retest_passed is not None else on_assessment(record, result)
        self.store.put(record)
        return record

    def concept_history(self, learner_id: str, concept: str) -> list[dict]:
        return concept_history(self.store, learner_id, concept)

    def target_concept(self, learner_id: str) -> str:
        return target_concept(self.store, learner_id)

    def next_question(self, learner_id: str, concept: str | None = None) -> tuple[Question, DifficultyDecision]:
        return plan_next_question(self.store, learner_id, concept)

    def finalize_interaction(
        self,
        learner_id: str,
        question: Question,
        response: LearnerResponse,
        initial: Diagnosis,
        final: Diagnosis,
        steps: list[ProbeStep],
    ) -> dict:
        record, mastery = self.confirm(learner_id, final, question)
        concept = mastery.concept if mastery else self.question_concept(question, final)
        decision = self.next_question(learner_id, concept)[1] if concept else None
        label = final.top_labels[0][0]
        explanation = explain(self.model, question, response, label) if self.model else {}
        thresholds = thresholds_for(self.model.kind if self.model else None)
        digest, trace = practice_trace(
            question, response, initial, final, steps, record, mastery, decision, explanation, thresholds
        )
        return self.store.trace(self.store.save_trace(learner_id, "practice", digest, trace))

    def _assessment_trace(
        self,
        learner_id: str,
        kind: str,
        misconception: str,
        before: LearnerRecord,
        after: LearnerRecord,
        result: AssessmentResult,
        updates: list[MasteryUpdate],
    ) -> dict:
        digest, trace = assessment_trace(kind, misconception, before, after, result, updates)
        return self.store.trace(self.store.save_trace(learner_id, kind, digest, trace))

    def profile(self, learner_id: str) -> list[dict]:
        return profile_rows(self.store, learner_id)
