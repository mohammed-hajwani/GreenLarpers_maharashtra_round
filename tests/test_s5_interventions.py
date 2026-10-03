from relearn.content import load_content
from relearn.intervention.builder import build_intervention
from relearn.intervention.checker import check_intervention
from relearn.intervention.selector import EXHAUSTED, select_strategy, strategy_order
from relearn.llm.cache import LLMCache
from relearn.llm.stub import StubLLMClient
from relearn.schemas import Intervention, LearnerResponse

RESPONSE = LearnerResponse(
    question_id="q", answer="6 N forward", working="it needs a force to keep moving at constant speed"
)


def test_every_strategy_valid() -> None:
    content = load_content()
    llm = StubLLMClient()
    for m in content.misconceptions:
        for strategy in strategy_order(m):
            for personalize in (False, True):
                iv = build_intervention(m, strategy, RESPONSE, [], llm, LLMCache(), personalize)
                assert check_intervention(iv), (m, strategy)


def test_checker_rejects() -> None:
    concept = load_content().misconceptions["M01"].correct_concept
    assert not check_intervention(
        Intervention(misconception="M01", strategy="x", text="", follow_up_prompt="")
    )
    long = Intervention(misconception="M01", strategy="x", text=concept + " word" * 300, follow_up_prompt="")
    assert not check_intervention(long)
    bad = Intervention(
        misconception="M01",
        strategy="x",
        text="Yes, it needs a force to keep moving. " + concept,
        follow_up_prompt="",
    )
    assert not check_intervention(bad)


def test_escalation() -> None:
    order = strategy_order("M01")
    assert select_strategy("M01", []) == order[0]
    assert select_strategy("M01", order[:1]) == order[1]
    assert select_strategy("M01", order) == EXHAUSTED


def test_cache_hit_on_repeat() -> None:
    cache = LLMCache()
    llm = StubLLMClient()
    build_intervention("M01", "counterexample", RESPONSE, [], llm, cache, True)
    build_intervention("M01", "counterexample", RESPONSE, [], llm, cache, True)
    assert llm.calls == 1
    assert cache.hits == 1
