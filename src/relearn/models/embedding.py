import hashlib
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import scipy.sparse as sps
from sklearn.base import ClassifierMixin
from sklearn.pipeline import FeatureUnion

from relearn.config import ROOT
from relearn.models.base import TextClassifier

DEFAULT_ENCODER = "sentence-transformers/all-MiniLM-L6-v2"
STEM_SEP = " [sep] "
WORK_SEP = " || "


def cache_dir() -> str:
    return os.environ.get("RELEARN_MODEL_CACHE", str(ROOT / ".cache" / "hf"))


@lru_cache(maxsize=2)
def get_encoder(name: str = DEFAULT_ENCODER):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name, device="cpu", cache_folder=cache_dir())


def text_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class EmbeddingCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.store: dict[str, np.ndarray] = {}
        if path and path.exists():
            data = np.load(path)
            self.store = {k: data[k] for k in data.files}

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(self.path, **self.store)


def embed(
    texts: list[str], encoder_name: str = DEFAULT_ENCODER, cache: EmbeddingCache | None = None
) -> np.ndarray:
    if cache is None:
        cache = EmbeddingCache()
    keys = [text_key(t) for t in texts]
    missing = sorted({t for t, k in zip(texts, keys, strict=True) if k not in cache.store})
    if missing:
        vectors = get_encoder(encoder_name).encode(
            missing, batch_size=64, normalize_embeddings=True, show_progress_bar=False
        )
        for t, v in zip(missing, vectors, strict=True):
            cache.store[text_key(t)] = np.asarray(v, dtype=np.float32)
    return np.stack([cache.store[k] for k in keys])


def split_text(text: str) -> tuple[str, str, str]:
    stem, _, rest = text.partition(STEM_SEP)
    answer, _, working = rest.partition(WORK_SEP)
    return stem, answer.strip(), working.strip()


def response_vectors(texts: list[str], encoder_name: str, cache: EmbeddingCache | None = None) -> np.ndarray:
    parts = [split_text(t) for t in texts]
    answers = embed([p[1] or "(empty)" for p in parts], encoder_name, cache)
    workings = embed([p[2] or "(empty)" for p in parts], encoder_name, cache)
    return np.hstack([answers, workings])


class EmbeddingModel(TextClassifier):
    name = "v1_embedding_minilm_hybrid"

    def __init__(
        self,
        clf: ClassifierMixin,
        encoder_name: str = DEFAULT_ENCODER,
        temperature: float = 1.0,
        version: str = "1",
        exemplars: dict[str, dict] | None = None,
        tfidf: FeatureUnion | None = None,
    ) -> None:
        self.clf = clf
        self.encoder_name = encoder_name
        self.temperature = temperature
        self.version = version
        self.exemplars = exemplars or {}
        self.tfidf = tfidf
        self.cache = EmbeddingCache()

    @property
    def labels(self) -> list[str]:
        return list(self.clf.classes_)

    def vectors(self, texts: list[str]) -> np.ndarray:
        return response_vectors(texts, self.encoder_name, self.cache)

    def design(self, texts: list[str], vectors: np.ndarray | None = None):
        v = self.vectors(texts) if vectors is None else vectors
        if self.tfidf is None:
            return v
        return sps.hstack([self.tfidf.transform(texts), sps.csr_matrix(v)]).tocsr()

    def logits_from_design(self, x) -> np.ndarray:
        if hasattr(self.clf, "decision_function"):
            return self.clf.decision_function(x)
        return np.log(np.clip(self.clf.predict_proba(x), 1e-9, 1.0))

    def logits(self, texts: list[str]) -> np.ndarray:
        return self.logits_from_design(self.design(texts))

    def similar_examples(self, text: str, label: str, k: int = 3) -> list[tuple[str, float]]:
        bank = self.exemplars.get(label)
        if not bank:
            return []
        v = self.vectors([text])[0]
        sims = (np.asarray(bank["vectors"]) @ v) / 2.0
        order = np.argsort(-sims)[:k]
        return [(bank["texts"][i], float(sims[i])) for i in order]

    def top_features(self, text: str, label: str, k: int = 6) -> list[tuple[str, float]]:
        if self.tfidf is None or not hasattr(self.clf, "coef_"):
            return []
        x = self.tfidf.transform([text]).tocoo()
        names = self.tfidf.get_feature_names_out()
        coef = self.clf.coef_[self.labels.index(label)]
        scored = sorted(
            (
                (names[j].split("__", 1)[-1], float(v * coef[j]))
                for j, v in zip(x.col, x.data, strict=True)
                if names[j].startswith("word__") and v * coef[j] > 0
            ),
            key=lambda x: -x[1],
        )
        return scored[:k]
