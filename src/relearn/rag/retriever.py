import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from relearn.config import ROOT
from relearn.content import load_content
from relearn.models.embedding import DEFAULT_ENCODER, embed

PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
INDEX_PATH = ROOT / ".cache" / "rag_index.npz"


@dataclass
class Passage:
    passage_id: str
    misconception: str
    source: str
    text: str


def build_corpus() -> list[Passage]:
    content = load_content()
    out = []
    for m, info in content.misconceptions.items():
        text = f"Misconception: {info.description}. Correct idea: {info.correct_concept}"
        out.append(Passage(f"{m}:definition", m, "misconceptions.yaml", text))
        for s in content.interventions[m]:
            text = PLACEHOLDER.sub("", s.template).replace('""', "").replace("  ", " ").strip()
            out.append(Passage(f"{m}:{s.strategy}", m, "interventions.yaml", text))
    for item in content.items:
        out.append(
            Passage(
                f"{item.misconception}:{item.item_id}",
                item.misconception,
                "item_bank.yaml",
                f"{item.stem} Correct answer: {item.correct_answer}.",
            )
        )
    return out


def _corpus_hash(corpus: list[Passage]) -> str:
    return hashlib.sha1("\x1f".join(p.passage_id + p.text for p in corpus).encode("utf-8")).hexdigest()


class Retriever:
    def __init__(self, encoder: str = DEFAULT_ENCODER) -> None:
        self.encoder = encoder
        self.corpus = build_corpus()
        digest = _corpus_hash(self.corpus)
        if INDEX_PATH.exists():
            data = np.load(INDEX_PATH)
            if str(data["digest"]) == digest:
                self.vectors = data["vectors"]
                return
        self.vectors = embed([p.text for p in self.corpus], encoder)
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(INDEX_PATH, vectors=self.vectors, digest=np.array(digest))

    def retrieve(self, query: str, misconception: str | None = None, k: int = 3) -> list[dict]:
        content = load_content()
        concept = content.concept_of(misconception) if misconception else None
        allowed = {m for m in content.misconceptions if concept is None or content.concept_of(m) == concept}
        q = embed([query], self.encoder)[0]
        scores = self.vectors @ q
        ranked = sorted(
            (i for i, p in enumerate(self.corpus) if p.misconception in allowed),
            key=lambda i: (-(scores[i] + (0.1 if self.corpus[i].misconception == misconception else 0.0)), i),
        )
        return [
            {
                "passage_id": self.corpus[i].passage_id,
                "source": self.corpus[i].source,
                "text": self.corpus[i].text,
                "cosine": float(scores[i]),
            }
            for i in ranked[:k]
        ]


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()
