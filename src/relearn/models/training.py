import random
from datetime import UTC, datetime

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from relearn.config import Config
from relearn.data.pipeline import dataset_fingerprint
from relearn.models.base import TextClassifier, softmax
from relearn.models.baseline import build_tfidf, texts_of, train_baseline
from relearn.models.calibration import expected_calibration_error, fit_temperature_from_logits
from relearn.models.embedding import EmbeddingCache, EmbeddingModel, response_vectors
from relearn.models.registry import BASELINE, EMBEDDING, save_model
from relearn.schemas import Sample


def _targets(model_labels: list[str], samples: list[Sample]) -> np.ndarray:
    return np.array([model_labels.index(s.misconception_label) for s in samples])


def calibrate(logits: np.ndarray, targets: np.ndarray) -> dict:
    t = fit_temperature_from_logits(logits, targets)
    return {
        "temperature": t,
        "val_ece_before": expected_calibration_error(softmax(logits), targets),
        "val_ece_after": expected_calibration_error(softmax(logits / t), targets),
    }


def _metadata(
    name: str, version: str, feature_method: str, model: TextClassifier, splits: dict, extra: dict
) -> dict:
    all_samples = splits["train"] + splits["val"] + splits["test"]
    return {
        "name": name,
        "version": version,
        "training_date": datetime.now(UTC).isoformat(timespec="seconds"),
        "training_dataset": {
            "data_provenance": "synthetic",
            "source": "content/question_templates rendered by data/generator.py, cleaned and deduplicated",
            "fingerprint": dataset_fingerprint(all_samples),
            "split_sizes": {k: len(v) for k, v in splits.items()},
            "split_method": "by question template",
        },
        "feature_method": feature_method,
        "classes": model.labels,
        **extra,
    }


def train_baseline_versioned(splits: dict[str, list[Sample]], cfg: Config) -> TextClassifier:
    model = train_baseline(splits["train"], cfg)
    val = splits["val"]
    cal = calibrate(model.logits(texts_of(val)), _targets(model.labels, val))
    model.temperature = cal["temperature"]
    val_pred = model.predict(texts_of(val))
    meta = _metadata(
        model.name,
        model.version,
        "TF-IDF word 1-2 grams + char_wb 3-5 grams, logistic regression (balanced)",
        model,
        splits,
        {
            "calibration": cal,
            "val_macro_f1": float(f1_score([s.misconception_label for s in val], val_pred, average="macro")),
        },
    )
    save_model(BASELINE, model, meta)
    return model


def _exemplars(train: list[Sample], vectors: np.ndarray, per_class: int, seed: int) -> dict:
    rng = random.Random(seed)
    by_label: dict[str, list[int]] = {}
    for i, s in enumerate(train):
        by_label.setdefault(s.misconception_label, []).append(i)
    out = {}
    texts = texts_of(train)
    for label, idx in by_label.items():
        chosen = sorted(rng.sample(idx, min(per_class, len(idx))))
        out[label] = {"texts": [texts[i] for i in chosen], "vectors": vectors[chosen].astype(np.float32)}
    return out


def train_embedding_versioned(
    splits: dict[str, list[Sample]], cfg: Config, cache: EmbeddingCache
) -> TextClassifier:
    e = cfg.embedding
    texts = {k: texts_of(v) for k, v in splits.items()}
    vectors = {k: response_vectors(v, e.encoder, cache) for k, v in texts.items()}
    y = {k: [s.misconception_label for s in v] for k, v in splits.items()}
    tfidf = build_tfidf(cfg).fit(texts["train"])
    lr = {"C": e.C, "max_iter": e.max_iter, "class_weight": "balanced", "random_state": cfg.seed}
    candidates = {
        "hybrid_tfidf_minilm_logreg": EmbeddingModel(LogisticRegression(**lr), e.encoder, tfidf=tfidf),
        "minilm_logreg": EmbeddingModel(LogisticRegression(**{**lr, "C": 1.0}), e.encoder),
    }
    if e.try_gradient_boosting:
        candidates["minilm_hist_gradient_boosting"] = EmbeddingModel(
            HistGradientBoostingClassifier(max_iter=200, class_weight="balanced", random_state=cfg.seed),
            e.encoder,
        )
    scores = {}
    for name, model in candidates.items():
        model.cache = cache
        model.clf.fit(model.design(texts["train"], vectors["train"]), y["train"])
        pred = model.logits_from_design(model.design(texts["val"], vectors["val"])).argmax(axis=1)
        scores[name] = float(f1_score(y["val"], [model.labels[i] for i in pred], average="macro"))
    best = max(scores, key=scores.get)
    model = candidates[best]
    model.exemplars = _exemplars(splits["train"], vectors["train"], e.exemplars_per_class, cfg.seed)
    val_logits = model.logits_from_design(model.design(texts["val"], vectors["val"]))
    cal = calibrate(val_logits, _targets(model.labels, splits["val"]))
    model.temperature = cal["temperature"]
    meta = _metadata(
        model.name,
        model.version,
        f"{best}: {e.encoder} embeddings of answer and working (2 x 384-d)"
        + (" + TF-IDF of stem, answer and working" if model.tfidf is not None else ""),
        model,
        splits,
        {
            "encoder": e.encoder,
            "classifier": best,
            "candidate_val_macro_f1": scores,
            "val_macro_f1": scores[best],
            "calibration": cal,
        },
    )
    model.cache = EmbeddingCache()
    save_model(EMBEDDING, model, meta)
    return model
