from collections.abc import Callable
from dataclasses import dataclass

from relearn.content import load_content
from relearn.learning.flow import LessonEngine, LessonFlow
from relearn.learning.items import practice_item

DEMO_LEARNER = "guided-demo"
DEMO_WRONG = ("2.7 N", "The force from the hit keeps it moving forward.")
DEMO_HELD = "M01"


@dataclass
class GuidedStep:
    label: str
    action: Callable[[LessonEngine, LessonFlow], None]


def start_demo(engine: LessonEngine) -> LessonFlow:
    engine.tutor.store.reset(DEMO_LEARNER)
    template = next(t for t in load_content().templates if t.template_id == "m09_kicked_ball_02")
    return engine.start(DEMO_LEARNER, "force_motion", item=practice_item(template, {"m": 0.45, "v": 6}))


def _answer_quick_checks(engine: LessonEngine, flow: LessonFlow) -> None:
    while flow.phase == "quick_check":
        probe = flow.pending["choice"].probe
        engine.answer_quick_check(flow, probe.expected_answer_by_label.get(DEMO_HELD, probe.options[0]))


def _wrong(engine: LessonEngine, flow: LessonFlow) -> None:
    engine.check(flow, *DEMO_WRONG)


def _right(engine: LessonEngine, flow: LessonFlow) -> None:
    engine.check(flow, flow.item.answer_display, flow.item.explanation)


def _item_right(engine: LessonEngine, flow: LessonFlow) -> None:
    engine.check(flow, flow.item.answer_display)


STEPS = [
    GuidedStep("A student answers with the idea that the kick keeps pushing the ball.", _wrong),
    GuidedStep("A quick check helps pin down the student's thinking.", _answer_quick_checks),
    GuidedStep("The student tries again with the same idea.", lambda e, f: e.try_again(f)),
    GuidedStep(
        "A second wrong answer brings a more explicit hint.", lambda e, f: (_wrong(e, f), _answer_quick_checks(e, f))
    ),
    GuidedStep("The student reveals the answer, with no penalty.", lambda e, f: e.reveal(f)),
    GuidedStep("A fresh question of the same type, not a repeat.", lambda e, f: e.try_another(f)),
    GuidedStep("Now the student gets it right.", _right),
    GuidedStep("Continue: one more to lock the idea in.", lambda e, f: e.continue_(f)),
    GuidedStep("Lock-in question 1.", _item_right),
    GuidedStep("Next.", lambda e, f: e.continue_(f)),
    GuidedStep("Lock-in question 2.", _item_right),
    GuidedStep("Next.", lambda e, f: e.continue_(f)),
    GuidedStep("Lock-in question 3.", _item_right),
    GuidedStep("Next.", lambda e, f: e.continue_(f)),
    GuidedStep("Lock-in question 4: the idea is locked in for now.", _item_right),
    GuidedStep("Continue the lesson with the next question.", lambda e, f: e.continue_(f)),
]
