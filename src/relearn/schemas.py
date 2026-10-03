from enum import Enum

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    mcq = "mcq"
    explanation = "explanation"
    numeric = "numeric"


class Question(BaseModel):
    question_id: str
    template_id: str
    question_type: QuestionType
    stem: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    concept_tags: list[str] = Field(default_factory=list)


class LearnerResponse(BaseModel):
    question_id: str
    answer: str
    working: str = ""


class Sample(BaseModel):
    sample_id: str
    question: Question
    response: LearnerResponse
    is_correct: bool
    misconception_label: str
    confusable_group: str | None = None
    rationale: str
    source: str


class Diagnosis(BaseModel):
    top_labels: list[tuple[str, float]]
    is_correct: bool
    ambiguous: bool
    confusable_group: str | None = None
    posterior: dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0
    entropy: float = 0.0
    route: str = "accept"
    model_name: str = ""
    model_version: str = ""

    @property
    def misconception(self) -> str | None:
        if self.is_correct:
            return None
        return next((label for label, _ in self.top_labels if label != "none"), None)

    @property
    def misconception_confidence(self) -> float:
        label = self.misconception
        return next((p for name, p in self.top_labels if name == label), 0.0)


class Probe(BaseModel):
    probe_id: str
    confusable_group: str
    stem: str
    options: list[str]
    expected_answer_by_label: dict[str, str]


class Intervention(BaseModel):
    misconception: str
    strategy: str
    text: str
    follow_up_prompt: str
    mode: str = "template"
    sources: list[dict] = Field(default_factory=list)
    modality: str = "text"


class AssessmentItem(BaseModel):
    item_id: str
    misconception: str
    kind: str
    stem: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    trap_answer_maps_to: dict[str, str] = Field(default_factory=dict)


class AssessmentResult(BaseModel):
    misconception: str
    transfer_correct: int
    transfer_total: int
    trap_passed: bool | None = None
    retest_passed: bool | None = None
    item_correct: dict[str, bool] = Field(default_factory=dict)


class MisconceptionState(str, Enum):
    unseen = "unseen"
    active = "active"
    intervened = "intervened"
    resolved = "resolved"
    relapsed = "relapsed"


class LearnerRecord(BaseModel):
    learner_id: str
    misconception: str
    state: MisconceptionState
    alpha: float
    beta: float
    strategies_tried: list[str]
    last_updated: str
