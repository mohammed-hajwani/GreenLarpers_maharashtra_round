import re
from dataclasses import dataclass, field

from relearn import services as svc
from relearn.content import load_content
from relearn.learning.hints import first_hint, generic_hint, key_idea
from relearn.learning.items import LessonItem, assessment_lesson_item, variant
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse

LESSON_LENGTH = 5
VISIT_CAP = 6
NORMALIZE = re.compile(r"\s+")


@dataclass
class Feedback:
    status: str
    message: str
    hint: str = ""
    answer: str = ""
    explanation: str = ""
    modality: str = "text"
    visual_for: str | None = None


@dataclass
class LessonFlow:
    learner_id: str
    concept: str
    phase: str = "question"
    item: LessonItem | None = None
    feedback: Feedback | None = None
    completed: int = 0
    checks: int = 0
    attempts_on_item: int = 0
    revealed: bool = False
    counted: bool = False
    seen: set[str] = field(default_factory=set)
    mix_up: str | None = None
    lockin: list = field(default_factory=list)
    lockin_answers: dict = field(default_factory=dict)
    lockin_total: int = 0
    lockin_done: bool = False
    pending: dict = field(default_factory=dict)
    seed: int = 0
    last_answer: str = ""
    explain_for: str | None = None

    @property
    def concept_name(self) -> str:
        return load_content().concepts[self.concept].name

    @property
    def progress(self) -> tuple[int, int]:
        return min(self.completed + (0 if self.phase == "complete" else 1), LESSON_LENGTH), LESSON_LENGTH


def _norm(text: str) -> str:
    return NORMALIZE.sub(" ", text.strip().lower().rstrip("."))


class LessonEngine:
    def __init__(self, tutor: Tutor) -> None:
        self.tutor = tutor

    def start(
        self, learner_id: str, concept: str | None = None, seen: set[str] | None = None, item: LessonItem | None = None
    ) -> LessonFlow:
        concept = concept or svc.next_question(self.tutor, learner_id)[1].concept
        flow = LessonFlow(learner_id=learner_id, concept=concept, seen=set(seen or ()), seed=len(seen or ()))
        if item is not None:
            self._present(flow, item)
            return flow
        self._next(flow)
        return flow

    def _present(self, flow: LessonFlow, item: LessonItem) -> None:
        flow.item, flow.feedback, flow.phase = item, None, "question"
        flow.attempts_on_item, flow.revealed, flow.counted, flow.pending = 0, False, False, {}
        flow.last_answer = ""
        flow.seen.add(item.question.question_id)

    def _practice(self, flow: LessonFlow, mix_up: str | None = None) -> LessonItem | None:
        planned = svc.next_question(self.tutor, flow.learner_id, flow.concept)[1].template_id
        flow.seed += 1
        return variant(flow.concept, mix_up, flow.seen, flow.seed, first=None if mix_up else planned)

    def _next(self, flow: LessonFlow) -> None:
        due = [(m, i) for m, i in svc.due_retests(self.tutor, flow.learner_id) if i.item_id not in flow.seen]
        if due:
            self._present(flow, assessment_lesson_item(due[0][1], "review"))
            return
        if flow.completed >= LESSON_LENGTH:
            flow.phase, flow.item, flow.feedback = "complete", None, None
            return
        item = self._practice(flow)
        if item is None:
            flow.phase, flow.item = "complete", None
            flow.feedback = Feedback("exhausted", "You've seen every question we have for this idea today. Nice work!")
            return
        self._present(flow, item)

    def check(self, flow: LessonFlow, answer: str, working: str = "") -> Feedback:
        item = flow.item
        flow.last_answer = answer
        if item.kind == "practice":
            return self._check_practice(flow, answer, working)
        correct = _norm(answer) == _norm(item.answer_display)
        flow.attempts_on_item += 1
        if item.kind == "lockin":
            return self._check_lockin(flow, answer, correct)
        return self._check_review(flow, answer, correct)

    def _check_practice(self, flow: LessonFlow, answer: str, working: str) -> Feedback:
        response = LearnerResponse(question_id=flow.item.question.question_id, answer=answer, working=working)
        problem = svc.screen(flow.item.question, response)
        if problem:
            flow.feedback = Feedback("needs_more", "Give it a go: write your best guess and a few words on why.")
            return flow.feedback
        flow.checks += 1
        flow.attempts_on_item += 1
        diagnosis = svc.diagnose(self.tutor, flow.learner_id, flow.item.question, response)
        flow.pending = {"response": response, "initial": diagnosis, "diagnosis": diagnosis, "steps": [], "used": set()}
        return self._advance_quick_check(flow)

    def _advance_quick_check(self, flow: LessonFlow) -> Feedback:
        p = flow.pending
        choice = svc.next_probe(self.tutor, p["diagnosis"], p["used"])
        if choice is not None:
            p["choice"] = choice
            flow.phase = "quick_check"
            flow.feedback = Feedback("quick_check", "Quick check")
            return flow.feedback
        return self._finish_practice(flow)

    def answer_quick_check(self, flow: LessonFlow, answer: str) -> Feedback:
        p = flow.pending
        p["used"].add(p["choice"].probe.probe_id)
        p["diagnosis"], step = svc.answer_probe(self.tutor, flow.learner_id, p["diagnosis"], p.pop("choice"), answer)
        p["steps"].append(step)
        return self._advance_quick_check(flow)

    def _finish_practice(self, flow: LessonFlow) -> Feedback:
        p, item = flow.pending, flow.item
        d = p["diagnosis"]
        svc.finalize(self.tutor, flow.learner_id, item.question, p["response"], p["initial"], d, p["steps"])
        flow.phase = "feedback"
        if d.is_correct:
            flow.feedback = Feedback("correct", "Nice work!", answer=item.answer_display, explanation=item.explanation)
            return flow.feedback
        mix_up = d.misconception
        flow.mix_up = mix_up or item.mix_up
        if flow.checks >= VISIT_CAP:
            return self._defer(flow)
        modality = "text"
        if mix_up:
            iv = svc.intervention(self.tutor, flow.learner_id, mix_up, p["response"])
            hint = first_hint(iv.text if iv else "", mix_up)
            modality = iv.modality if iv else "text"
        else:
            hint = generic_hint()
        if flow.attempts_on_item >= 2:
            hint = f"{hint} {key_idea(flow.mix_up)}".strip()
        flow.feedback = Feedback(
            "incorrect", "Let's work through this.", hint=hint, modality=modality, visual_for=mix_up
        )
        return flow.feedback

    def _defer(self, flow: LessonFlow) -> Feedback:
        svc.log_event(self.tutor, flow.learner_id, "review_flag", flow.concept, flow.mix_up, {"checks": flow.checks})
        flow.phase = "deferred"
        flow.feedback = Feedback("deferred", "Let's come back to this later. We'll keep going with the lesson.")
        return flow.feedback

    def try_again(self, flow: LessonFlow) -> None:
        if flow.revealed or flow.phase not in ("feedback",):
            return
        flow.phase, flow.feedback, flow.pending = "question", None, {}

    def reveal(self, flow: LessonFlow) -> Feedback:
        item = flow.item
        svc.log_event(
            self.tutor,
            flow.learner_id,
            "reveal",
            item.question.question_id,
            flow.mix_up,
            {"revealed": True, "concept": flow.concept},
        )
        flow.revealed, flow.phase = True, "feedback"
        flow.feedback = Feedback(
            "revealed",
            "Here's the answer.",
            answer=item.answer_display,
            explanation=item.explanation,
            modality="diagram",
            visual_for=flow.mix_up or item.mix_up,
        )
        return flow.feedback

    def try_another(self, flow: LessonFlow) -> Feedback | None:
        item = self._practice(flow, flow.mix_up or (flow.item.mix_up if flow.item else None))
        if item is None:
            flow.feedback = Feedback(
                "exhausted", "That's every version we have of this one. Let's keep going with the lesson."
            )
            return flow.feedback
        self._present(flow, item)
        return None

    def continue_(self, flow: LessonFlow) -> None:
        if flow.item is not None and flow.item.kind == "practice" and not flow.counted:
            flow.completed += 1
            flow.counted = True
        if flow.phase == "deferred":
            flow.completed = LESSON_LENGTH
        if self._needs_lockin(flow):
            self._start_lockin(flow)
            return
        if flow.lockin:
            self._present(flow, flow.lockin.pop(0))
            return
        if flow.explain_for and flow.phase != "explain":
            flow.phase, flow.feedback = "explain", None
            return
        flow.explain_for = None
        self._next(flow)

    def check_explanation(self, flow: LessonFlow, text: str) -> Feedback:
        status, _ = svc.check_explanation(self.tutor, flow.learner_id, flow.explain_for, text)
        key = key_idea(flow.explain_for)
        flow.feedback = {
            "needs_more": Feedback("needs_more", "Write a sentence or two in your own words."),
            "clear": Feedback("explain_clear", "Nice, that's the idea in your own words."),
            "partly": Feedback("explain_partly", "Almost there. Make sure it says this:", hint=key),
            "tricky": Feedback("explain_tricky", "Part of that still leans on the tricky idea.", hint=key),
        }[status]
        return flow.feedback

    def skip_explanation(self, flow: LessonFlow) -> None:
        flow.explain_for = None
        self._next(flow)

    def _needs_lockin(self, flow: LessonFlow) -> bool:
        if flow.lockin or flow.phase == "deferred" or not flow.feedback or flow.feedback.status != "correct":
            return False
        if flow.item.kind != "practice" or not flow.mix_up:
            return False
        state = svc.misconception_states(self.tutor, flow.learner_id).get(flow.mix_up)
        return state == "intervened" and svc.pending_retest(self.tutor, flow.learner_id, flow.mix_up) is None

    def _start_lockin(self, flow: LessonFlow) -> None:
        items = svc.plan_assessment(self.tutor, flow.learner_id, flow.mix_up)
        flow.lockin = [assessment_lesson_item(i, "lockin") for i in items]
        flow.lockin_total, flow.lockin_answers = len(flow.lockin), {}
        self._present(flow, flow.lockin.pop(0))

    def _check_lockin(self, flow: LessonFlow, answer: str, correct: bool) -> Feedback:
        item = flow.item
        flow.lockin_answers[item.assessment_item.item_id] = answer
        flow.phase = "feedback"
        message = "You're getting it." if correct else "Not quite. Here's the answer."
        flow.feedback = Feedback(
            "correct" if correct else "incorrect_item",
            message,
            answer=item.answer_display,
            explanation=item.explanation,
        )
        if flow.lockin:
            return flow.feedback
        bank = {i.item_id: i for i in load_content().items}
        items = [bank[i] for i in flow.lockin_answers]
        _, record = svc.submit_assessment(self.tutor, flow.learner_id, item.mix_up, items, flow.lockin_answers)
        if record.state.value == "intervened":
            flow.feedback.message += " Locked in for now. We'll check back on this later."
            flow.explain_for = item.mix_up
        else:
            flow.feedback.message += " Almost there. Let's look at this idea once more."
        flow.lockin_answers = {}
        return flow.feedback

    def _check_review(self, flow: LessonFlow, answer: str, correct: bool) -> Feedback:
        item = flow.item
        _, record = svc.submit_retest(self.tutor, flow.learner_id, item.assessment_item, answer)
        flow.phase = "feedback"
        if record.state.value == "resolved":
            message = "Nice work! That idea is locked in."
        else:
            message = "Good effort. We'll keep practising this idea."
        flow.feedback = Feedback(
            "correct" if correct else "incorrect_item",
            message,
            answer=item.answer_display,
            explanation=item.explanation,
        )
        return flow.feedback
