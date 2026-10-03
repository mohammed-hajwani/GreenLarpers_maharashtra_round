import re

from relearn.config import load_config
from relearn.content import load_content
from relearn.schemas import Intervention

QUOTED = re.compile(r'["“][^"”]*["”]|(?<=\s)\'[^\']*\'(?=\s)')


def check_intervention(intervention: Intervention) -> bool:
    text = intervention.text.strip()
    if not text:
        return False
    if len(text.split()) > load_config().intervention.max_words:
        return False
    info = load_content().misconceptions.get(intervention.misconception)
    if info is None or info.correct_concept not in text:
        return False
    own_words = QUOTED.sub("", text).lower()
    return not any(claim.lower() in own_words for claim in info.forbidden_claims)
