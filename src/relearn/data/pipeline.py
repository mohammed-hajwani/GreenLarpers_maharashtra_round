import hashlib
import re

from relearn.config import Config
from relearn.data.generator import generate_dataset
from relearn.data.splits import split_by_template
from relearn.schemas import Sample

SPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    return SPACE.sub(" ", text).strip()


def clean(samples: list[Sample]) -> list[Sample]:
    out = []
    for s in samples:
        response = s.response.model_copy(
            update={"answer": clean_text(s.response.answer), "working": clean_text(s.response.working)}
        )
        out.append(s.model_copy(update={"response": response}))
    return out


def dedup_key(s: Sample) -> str:
    raw = "\x1f".join(
        [s.question.stem.lower(), s.response.answer.lower(), s.response.working.lower(), s.misconception_label]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def deduplicate(samples: list[Sample]) -> list[Sample]:
    seen: set[str] = set()
    out = []
    for s in samples:
        key = dedup_key(s)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def dataset_fingerprint(samples: list[Sample]) -> str:
    h = hashlib.sha1()
    for s in samples:
        h.update(dedup_key(s).encode("utf-8"))
    return h.hexdigest()[:12]


def build_splits(cfg: Config) -> dict[str, list[Sample]]:
    return split_by_template(deduplicate(clean(generate_dataset(cfg))), cfg)
