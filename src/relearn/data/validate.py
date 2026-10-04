from collections import Counter

from relearn.config import Config
from relearn.content import load_content
from relearn.schemas import QuestionType, Sample


def dataset_stats(samples: list[Sample]) -> dict:
    labels = Counter(s.misconception_label for s in samples)
    groups = Counter(s.confusable_group for s in samples if s.confusable_group)
    return {
        "total": len(samples),
        "labels": dict(labels),
        "imbalance": max(labels.values()) / min(labels.values()),
        "confusable_groups": dict(groups),
    }


def validate_dataset(samples: list[Sample], splits: dict[str, list[Sample]], cfg: Config) -> list[str]:
    content = load_content()
    errors: list[str] = []
    ids = Counter(s.sample_id for s in samples)
    errors.extend(f"duplicate sample_id {k}" for k, v in ids.items() if v > 1)
    seen: dict[str, str] = {}
    for name, items in splits.items():
        for s in items:
            prev = seen.setdefault(s.question.template_id, name)
            if prev != name:
                errors.append(f"template {s.question.template_id} in {prev} and {name}")
    valid = set(content.labels())
    for s in samples:
        if s.misconception_label not in valid:
            errors.append(f"unknown label {s.misconception_label} in {s.sample_id}")
        if s.is_correct != (s.misconception_label == "none"):
            errors.append(f"correctness mismatch in {s.sample_id}")
        group = content.group_of(s.misconception_label)
        template = next(t for t in content.templates if t.template_id == s.question.template_id)
        if group and template.confusable_group == group and s.confusable_group != group:
            errors.append(f"missing confusable_group in {s.sample_id}")
        if s.question.question_type == QuestionType.mcq:
            if s.question.correct_answer not in s.question.options:
                errors.append(f"correct answer not in options for {s.sample_id}")
            if s.response.answer not in s.question.options:
                errors.append(f"response not in options for {s.sample_id}")
    stats = dataset_stats(samples)
    if stats["total"] < cfg.data.min_total_samples:
        errors.append(f"only {stats['total']} samples")
    if stats["imbalance"] > cfg.data.max_class_imbalance:
        errors.append(f"class imbalance {stats['imbalance']:.2f}")
    return errors
