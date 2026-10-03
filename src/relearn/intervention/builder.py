from relearn.config import load_config
from relearn.content import load_content
from relearn.llm.base import LLMClient
from relearn.llm.cache import LLMCache, content_hash
from relearn.schemas import Intervention, LearnerRecord, LearnerResponse

SYSTEM = (
    "You write two or three warm sentences to a physics learner that reference their answer. "
    "Do not state any physics facts beyond what is given."
)

DEFAULT_CACHE = LLMCache()


def personal_wrapper(
    misconception: str,
    strategy: str,
    template: str,
    response: LearnerResponse,
    llm: LLMClient,
    cache: LLMCache,
) -> str:
    key = content_hash(misconception, strategy, content_hash(template))
    cached = cache.get(key)
    if cached is not None:
        return cached
    text = llm.complete(SYSTEM, f"Learner answer: {response.answer}\nLearner working: {response.working}")
    cache.put(key, text)
    return text


def build_intervention(
    misconception: str,
    strategy: str,
    response: LearnerResponse,
    history: list[LearnerRecord],
    llm: LLMClient,
    cache: LLMCache | None = None,
    personalize: bool | None = None,
) -> Intervention:
    content = load_content()
    spec = next(s for s in content.interventions[misconception] if s.strategy == strategy)
    text = spec.template.format(
        learner_answer=response.answer.strip() or "(no answer)",
        learner_working=response.working.strip() or "(no working)",
        correct_concept=content.misconceptions[misconception].correct_concept,
    )
    if load_config().intervention.llm_personalize if personalize is None else personalize:
        wrapper = personal_wrapper(
            misconception, strategy, spec.template, response, llm, cache or DEFAULT_CACHE
        )
        text = wrapper + " " + text
    return Intervention(
        misconception=misconception, strategy=strategy, text=text, follow_up_prompt=spec.follow_up_prompt
    )
