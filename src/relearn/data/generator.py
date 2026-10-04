import itertools
import math
import random
from collections import Counter

from relearn.config import Config
from relearn.content import AnswerRule, Content, TemplateSpec, load_content
from relearn.data.render import render
from relearn.schemas import LearnerResponse, Question, Sample

NONE = "none"


def _label_template_counts(content: Content) -> Counter:
    counts: Counter = Counter()
    for t in content.templates:
        counts[NONE] += 1
        counts.update(t.wrong.keys())
    return counts


def _working(rng: random.Random, prefixes: list[str], rule: AnswerRule, params: dict) -> str:
    text = render(rng.choice(rule.working), params)
    prefix = rng.choice(prefixes)
    if prefix:
        text = prefix + text[0].lower() + text[1:]
    return text


def make_question(t: TemplateSpec, params: dict) -> Question:
    key = "_".join(f"{k}{params[k]}" for k in sorted(params))
    return Question(
        question_id=f"{t.template_id}__{key}",
        template_id=t.template_id,
        question_type=t.question_type,
        stem=render(t.stem, params),
        options=[render(o, params) for o in t.options],
        correct_answer=render(t.correct.answer, params),
        concept_tags=t.concept_tags,
    )


def _samples_for(
    t: TemplateSpec, label: str, rule: AnswerRule, n: int, rng: random.Random, content: Content
) -> list[Sample]:
    keys = list(t.params)
    combos = list(itertools.product(*(t.params[k] for k in keys)))
    group_members = content.confusable_groups.get(t.confusable_group or "", [])
    group = t.confusable_group if label in group_members else None
    rationale = rule.rationale or "Correct reasoning."
    out = []
    for k in range(n):
        params = dict(zip(keys, rng.choice(combos), strict=True))
        question = make_question(t, params)
        response = LearnerResponse(
            question_id=question.question_id,
            answer=render(rule.answer, params),
            working=_working(rng, content.working_prefixes, rule, params),
        )
        out.append(
            Sample(
                sample_id=f"{t.template_id}__{label}__{k:03d}",
                question=question,
                response=response,
                is_correct=label == NONE,
                misconception_label=label,
                confusable_group=group,
                rationale=rationale,
                source="template",
            )
        )
    return out


def generate_dataset(cfg: Config) -> list[Sample]:
    content = load_content()
    rng = random.Random(cfg.seed)
    counts = _label_template_counts(content)
    per_template = {label: math.ceil(cfg.data.target_per_label / c) for label, c in counts.items()}
    samples: list[Sample] = []
    for t in content.templates:
        rules = [(NONE, t.correct)] + sorted(t.wrong.items())
        for label, rule in rules:
            samples.extend(_samples_for(t, label, rule, per_template[label], rng, content))
    return samples
