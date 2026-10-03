import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from relearn.config import Config
from relearn.schemas import LearnerResponse, Question, Sample


def sample_text(question: Question, response: LearnerResponse) -> str:
    return f"{question.stem} [SEP] {response.answer} {response.working}".lower()


def texts_of(samples: list[Sample]) -> list[str]:
    return [sample_text(s.question, s.response) for s in samples]


class BaselineModel:
    def __init__(self, pipeline: Pipeline, temperature: float = 1.0) -> None:
        self.pipeline = pipeline
        self.temperature = temperature

    @property
    def labels(self) -> list[str]:
        return list(self.pipeline.classes_)

    def logits(self, texts: list[str]) -> np.ndarray:
        return self.pipeline.decision_function(texts)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        z = self.logits(texts) / self.temperature
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def predict(self, texts: list[str]) -> list[str]:
        idx = self.predict_proba(texts).argmax(axis=1)
        return [self.labels[i] for i in idx]


def train_baseline(train: list[Sample], cfg: Config) -> BaselineModel:
    b = cfg.baseline
    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, b.word_ngram_max), sublinear_tf=True)),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(b.char_ngram_min, b.char_ngram_max), sublinear_tf=True
                ),
            ),
        ]
    )
    clf = LogisticRegression(C=b.C, max_iter=b.max_iter, class_weight="balanced", random_state=cfg.seed)
    pipeline = Pipeline([("features", features), ("clf", clf)])
    pipeline.fit(texts_of(train), [s.misconception_label for s in train])
    return BaselineModel(pipeline)
