from relearn.config import load_config
from relearn.content import load_content
from relearn.schemas import AssessmentItem


def _pick(pool: list[AssessmentItem], seen: set[str], n: int) -> list[AssessmentItem]:
    unseen = [i for i in pool if i.item_id not in seen]
    reused = [i for i in pool if i.item_id in seen]
    return (unseen + reused)[:n]


def _bank(misconception: str, kind: str) -> list[AssessmentItem]:
    return [i for i in load_content().items if i.misconception == misconception and i.kind == kind]


def plan_assessment(misconception: str, seen: set[str] | None = None) -> list[AssessmentItem]:
    a = load_config().assessment
    seen = seen or set()
    return _pick(_bank(misconception, "transfer"), seen, a.transfer_count) + _pick(
        _bank(misconception, "trap"), seen, a.trap_count
    )


def plan_retest(misconception: str, seen: set[str] | None = None) -> AssessmentItem:
    return _pick(_bank(misconception, "retest"), seen or set(), 1)[0]
