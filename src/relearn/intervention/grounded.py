from relearn.config import load_config
from relearn.content import load_content
from relearn.intervention.builder import build_intervention
from relearn.intervention.checker import check_intervention
from relearn.llm.base import LLMClient
from relearn.llm.stub import StubLLMClient
from relearn.schemas import Intervention, LearnerResponse

SYSTEM = (
    "You are a physics tutor writing one short targeted intervention for a single misconception. "
    "Use only the facts in the provided passages; do not add any other physics claims. "
    "Address the learner's own answer directly, in at most 120 words. "
    "End with the exact correct-concept sentence you are given, copied verbatim."
)


def _prompt(
    misconception: str, strategy: str, response: LearnerResponse, mastery: float | None, passages: list[dict]
) -> str:
    info = load_content().misconceptions[misconception]
    lines = [f"[{i + 1}] {p['text']}" for i, p in enumerate(passages)]
    level = "unknown" if mastery is None else f"{mastery:.0%}"
    return (
        f"Misconception: {info.description}\n"
        f"Strategy: {strategy}\n"
        f"Learner mastery of this concept: {level}\n"
        f"Learner answer: {response.answer}\n"
        f"Learner working: {response.working}\n"
        f"Correct-concept sentence: {info.correct_concept}\n"
        "Passages:\n" + "\n".join(lines)
    )


def _template_with_sources(base: Intervention, passages: list[dict]) -> Intervention:
    extra = next((p for p in passages if p["text"] not in base.text and "item_bank" not in p["source"]), None)
    text = base.text
    if extra:
        candidate = f"{text} Related idea: {extra['text']}"
        trial = base.model_copy(update={"text": candidate})
        if check_intervention(trial):
            text = candidate
    return base.model_copy(update={"text": text})


def build_grounded_intervention(
    misconception: str,
    strategy: str,
    response: LearnerResponse,
    llm: LLMClient,
    passages: list[dict],
    mastery: float | None = None,
) -> tuple[Intervention, str]:
    base = build_intervention(misconception, strategy, response, [], llm, personalize=False)
    if not isinstance(llm, StubLLMClient):
        try:
            text = llm.complete(SYSTEM, _prompt(misconception, strategy, response, mastery, passages), max_tokens=1024)
            candidate = base.model_copy(update={"text": text.strip()})
            words = len(candidate.text.split())
            if check_intervention(candidate) and words <= load_config().intervention.max_words:
                return candidate, "llm_grounded"
        except Exception:
            pass
    return _template_with_sources(base, passages), "template_with_retrieval"
