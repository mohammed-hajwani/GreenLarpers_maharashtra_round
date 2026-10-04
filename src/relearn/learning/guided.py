from collections.abc import Callable
from dataclasses import dataclass

from relearn.content import load_content
from relearn.learning.flow import LessonEngine, LessonFlow
from relearn.learning.items import practice_item

DEMO_LEARNER = "guided-demo"
DEMO_WRONG = ("2.7 N", "The force from the hit keeps it moving forward.")
DEMO_HELD = "M01"


Entry = tuple[str, str]


@dataclass
class GuidedStep:
    label: str
    action: Callable[[LessonEngine, LessonFlow], list[Entry]]


def start_demo(engine: LessonEngine) -> LessonFlow:
    engine.tutor.store.reset(DEMO_LEARNER)
    template = next(t for t in load_content().templates if t.template_id == "m09_kicked_ball_02")
    return engine.start(DEMO_LEARNER, "force_motion", item=practice_item(template, {"m": 0.45, "v": 6}))


def _answer_quick_checks(engine: LessonEngine, flow: LessonFlow) -> list[Entry]:
    entries = []
    while flow.phase == "quick_check":
        probe = flow.pending["choice"].probe
        choice = probe.expected_answer_by_label.get(DEMO_HELD, probe.options[0])
        entries += [("Quick check", probe.stem), ("Picked", choice)]
        engine.answer_quick_check(flow, choice)
    return entries


def _wrong(engine: LessonEngine, flow: LessonFlow) -> list[Entry]:
    engine.check(flow, *DEMO_WRONG)
    return [("Answer", DEMO_WRONG[0]), ("Thinking", DEMO_WRONG[1])]


def _wrong_again(engine: LessonEngine, flow: LessonFlow) -> list[Entry]:
    return _wrong(engine, flow) + _answer_quick_checks(engine, flow)


def _right(engine: LessonEngine, flow: LessonFlow) -> list[Entry]:
    answer, thinking = flow.item.answer_display, flow.item.explanation
    engine.check(flow, answer, thinking)
    return [("Answer", answer), ("Thinking", thinking)]


def _item_right(engine: LessonEngine, flow: LessonFlow) -> list[Entry]:
    stem, answer = flow.item.question.stem, flow.item.answer_display
    engine.check(flow, answer)
    return [("Question", stem), ("Answer", answer)]


def _click(label: str, method: str) -> Callable[[LessonEngine, LessonFlow], list[Entry]]:
    def run(engine: LessonEngine, flow: LessonFlow) -> list[Entry]:
        getattr(engine, method)(flow)
        return [("Clicked", label)]

    return run


DEMO_EXPLANATION = (
    "Once it is moving it keeps a steady speed on its own because of inertia. "
    "The forces are balanced so the net force is zero."
)


def _explain(engine: LessonEngine, flow: LessonFlow) -> list[Entry]:
    engine.check_explanation(flow, DEMO_EXPLANATION)
    return [("Explanation", DEMO_EXPLANATION)]


CONTINUE = _click("Continue", "continue_")
STEPS = [
    GuidedStep("A student answers with the idea that the kick keeps pushing the ball.", _wrong),
    GuidedStep("A quick check helps pin down the student's thinking.", _answer_quick_checks),
    GuidedStep("The student tries again with the same idea.", _click("Try again", "try_again")),
    GuidedStep("A second wrong answer brings a more explicit hint.", _wrong_again),
    GuidedStep("The student reveals the answer, with no penalty.", _click("Reveal answer", "reveal")),
    GuidedStep(
        "A fresh question of the same type, not a repeat.", _click("Try another question of this type", "try_another")
    ),
    GuidedStep("Now the student gets it right.", _right),
    GuidedStep("Continue: one more to lock the idea in.", CONTINUE),
    GuidedStep("Lock-in question 1.", _item_right),
    GuidedStep("Next.", CONTINUE),
    GuidedStep("Lock-in question 2.", _item_right),
    GuidedStep("Next.", CONTINUE),
    GuidedStep("Lock-in question 3.", _item_right),
    GuidedStep("Next.", CONTINUE),
    GuidedStep("Lock-in question 4: the idea is locked in for now.", _item_right),
    GuidedStep("Continue: explain the idea back in your own words.", CONTINUE),
    GuidedStep("The student explains it in their own words.", _explain),
    GuidedStep("Continue the lesson with the next question.", CONTINUE),
]
