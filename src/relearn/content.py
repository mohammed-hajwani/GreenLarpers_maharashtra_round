from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from relearn.config import load_config
from relearn.schemas import AssessmentItem, Probe, QuestionType

ALLOWED_STRATEGIES = {
    "counterexample",
    "cognitive_conflict",
    "fbd_walkthrough",
    "predict_then_check",
    "worked_example",
    "analogy",
}


class MisconceptionInfo(BaseModel):
    id: str
    label: str
    description: str
    confusable_group: str | None = None
    correct_concept: str
    forbidden_claims: list[str] = Field(default_factory=list)


class AnswerRule(BaseModel):
    answer: str
    working: list[str]
    rationale: str = ""


class TemplateSpec(BaseModel):
    template_id: str
    primary: str
    question_type: QuestionType
    confusable_group: str | None = None
    concept_tags: list[str] = Field(default_factory=list)
    stem: str
    params: dict[str, list[float | int]]
    options: list[str] = Field(default_factory=list)
    correct: AnswerRule
    wrong: dict[str, AnswerRule]


class StrategySpec(BaseModel):
    strategy: str
    template: str
    follow_up_prompt: str


class Content(BaseModel):
    working_prefixes: list[str]
    misconceptions: dict[str, MisconceptionInfo]
    confusable_groups: dict[str, list[str]]
    templates: list[TemplateSpec]
    probes: list[Probe]
    interventions: dict[str, list[StrategySpec]]
    items: list[AssessmentItem]

    def group_of(self, label: str) -> str | None:
        info = self.misconceptions.get(label)
        return info.confusable_group if info else None

    def labels(self) -> list[str]:
        return sorted(self.misconceptions) + ["none"]


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@lru_cache(maxsize=1)
def load_content() -> Content:
    root = load_config().path("content_dir")
    tax = _load(root / "misconceptions.yaml")
    templates = []
    for path in sorted((root / "question_templates").glob("*.yaml")):
        templates.extend(TemplateSpec.model_validate(t) for t in _load(path)["templates"])
    return Content(
        working_prefixes=tax["working_prefixes"],
        misconceptions={m["id"]: MisconceptionInfo.model_validate(m) for m in tax["misconceptions"]},
        confusable_groups=tax["confusable_groups"],
        templates=templates,
        probes=[Probe.model_validate(p) for p in _load(root / "probes.yaml")["probes"]],
        interventions={
            k: [StrategySpec.model_validate(s) for s in v]
            for k, v in _load(root / "interventions.yaml")["interventions"].items()
        },
        items=[AssessmentItem.model_validate(i) for i in _load(root / "item_bank.yaml")["items"]],
    )
