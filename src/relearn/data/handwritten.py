from functools import lru_cache

import yaml

from relearn.config import load_config
from relearn.content import load_content
from relearn.schemas import LearnerResponse, Question, QuestionType, Sample


@lru_cache(maxsize=1)
def load_handwritten() -> list[Sample]:
    path = load_config().path("content_dir") / "handwritten_test.yaml"
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)["items"]
    content = load_content()
    out = []
    for item in raw:
        question = Question(
            question_id=item["id"],
            template_id="handwritten",
            question_type=QuestionType(item["question_type"]),
            stem=item["stem"],
            options=item.get("options", []),
            correct_answer=item["correct_answer"],
        )
        label = item["label"]
        out.append(
            Sample(
                sample_id=item["id"],
                question=question,
                response=LearnerResponse(question_id=item["id"], answer=item["answer"], working=item["working"]),
                is_correct=label == "none",
                misconception_label=label,
                confusable_group=content.group_of(label),
                rationale="hand-written",
                source="handwritten",
            )
        )
    return out
