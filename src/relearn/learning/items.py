import itertools
import random
from dataclasses import dataclass, field

from relearn.content import TemplateSpec, load_content
from relearn.data.generator import make_question
from relearn.data.render import render
from relearn.schemas import AssessmentItem, Question, QuestionType


@dataclass
class LessonItem:
    kind: str
    question: Question
    answer_display: str
    explanation: str
    mix_up: str | None = None
    assessment_item: AssessmentItem | None = None
    template_id: str = ""
    extra: dict = field(default_factory=dict)


def _templates_for(concept: str, mix_up: str | None, first: str | None) -> list[TemplateSpec]:
    content = load_content()
    pool = [t for t in content.templates if content.concept_of(t.primary) == concept]
    same = [t for t in pool if mix_up and (t.primary == mix_up or mix_up in t.wrong)]
    rest = [t for t in pool if t not in same]
    ordered = same + rest
    if first:
        ordered.sort(key=lambda t: t.template_id != first)
    return ordered


def practice_item(template: TemplateSpec, params: dict) -> LessonItem:
    question = make_question(template, params)
    return LessonItem(
        kind="practice",
        question=question,
        answer_display=question.correct_answer,
        explanation=render(template.correct.working[0], params),
        mix_up=template.primary,
        template_id=template.template_id,
    )


def variant(concept: str, mix_up: str | None, seen: set[str], seed: int, first: str | None = None) -> LessonItem | None:
    for template in _templates_for(concept, mix_up, first):
        keys = list(template.params)
        combos = list(itertools.product(*(template.params[k] for k in keys)))
        random.Random(f"{seed}-{template.template_id}").shuffle(combos)
        for combo in combos:
            params = dict(zip(keys, combo, strict=True))
            item = practice_item(template, params)
            if item.question.question_id not in seen:
                return item
    return None


def assessment_lesson_item(item: AssessmentItem, kind: str) -> LessonItem:
    content = load_content()
    question = Question(
        question_id=item.item_id,
        template_id=f"item:{item.item_id}",
        question_type=QuestionType.mcq,
        stem=item.stem,
        options=list(item.options),
        correct_answer=item.correct_answer,
    )
    return LessonItem(
        kind=kind,
        question=question,
        answer_display=item.correct_answer,
        explanation=content.misconceptions[item.misconception].correct_concept,
        mix_up=item.misconception,
        assessment_item=item,
    )
