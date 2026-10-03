from relearn.config import load_config
from relearn.content import load_content

EXHAUSTED = "flag_for_human"


def strategy_order(misconception: str) -> list[str]:
    cap = load_config().escalation.max_strategies_per_misconception
    return [s.strategy for s in load_content().interventions[misconception]][:cap]


def select_strategy(misconception: str, strategies_tried: list[str]) -> str:
    for strategy in strategy_order(misconception):
        if strategy not in strategies_tried:
            return strategy
    return EXHAUSTED
