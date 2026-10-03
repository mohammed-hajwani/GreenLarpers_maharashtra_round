import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from relearn.config import Config
from relearn.models.base import TextClassifier
from relearn.schemas import LearnerResponse, Question, Sample


def sample_text(question: Question, response: LearnerResponse) -> str:
    return f"{question.stem} [SEP] {response.answer} || {response.working}".lower()


def texts_of(samples: list[Sample]) -> list[str]:
    return [sample_text(s.question, s.response) for s in samples]


class BaselineModel(TextClassifier):
    name = "baseline_tfidf_logreg"

    def __init__(self, pipeline: Pipeline, temperature: float = 1.0, version: str = "1") -> None:
        self.pipeline = pipeline
        self.temperature = temperature
        self.version = version

    @property
    def labels(self) -> list[str]:
        return list(self.pipeline.classes_)

    def logits(self, texts: list[str]) -> np.ndarray:
        return self.pipeline.decision_function(texts)

    def top_features(self, text: str, label: str, k: int = 6) -> list[tuple[str, float]]:
        features = self.pipeline.named_steps["features"]
        clf = self.pipeline.named_steps["clf"]
        x = features.transform([text]).tocoo()
        names = features.get_feature_names_out()
        coef = clf.coef_[self.labels.index(label)]
        scored = [(names[j], float(v * coef[j])) for j, v in zip(x.col, x.data, strict=True)]
        scored = [(n.split("__", 1)[-1].strip(), s) for n, s in scored if s > 0 and n.startswith("word__")]
        best: dict[str, float] = {}
        for n, s in sorted(scored, key=lambda x: -x[1]):
            if n and n not in best:
                best[n] = s
        return list(best.items())[:k]


def build_tfidf(cfg: Config) -> FeatureUnion:
    b = cfg.baseline
    return FeatureUnion(
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


def train_baseline(train: list[Sample], cfg: Config) -> BaselineModel:
    b = cfg.baseline
    clf = LogisticRegression(C=b.C, max_iter=b.max_iter, class_weight="balanced", random_state=cfg.seed)
    pipeline = Pipeline([("features", build_tfidf(cfg)), ("clf", clf)])
    pipeline.fit(texts_of(train), [s.misconception_label for s in train])
    return BaselineModel(pipeline)
