import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from relearn.config import Config
from relearn.models.base import softmax
from relearn.models.baseline import build_tfidf, texts_of
from relearn.models.embedding import EmbeddingCache, EmbeddingModel, response_vectors
from relearn.models.inference import NONE
from relearn.schemas import Sample

TARGET_FALSE_FLAG = 0.10


def _model(cfg: Config) -> EmbeddingModel:
    return EmbeddingModel(
        LogisticRegression(
            C=cfg.embedding.C, max_iter=cfg.embedding.max_iter, class_weight="balanced", random_state=cfg.seed
        ),
        cfg.embedding.encoder,
        tfidf=build_tfidf(cfg),
    )


def rank(a: np.ndarray) -> np.ndarray:
    return a.argsort().argsort() / max(len(a) - 1, 1)


def novelty_scores(
    model: EmbeddingModel, texts: list[str], vectors: np.ndarray, bank: np.ndarray
) -> dict[str, np.ndarray]:
    probs = softmax(model.logits_from_design(model.design(texts, vectors)))
    mis = [i for i, label in enumerate(model.labels) if label != NONE]
    msp = 1.0 - probs[:, mis].max(axis=1)
    sims = (vectors @ bank.T) / 2.0
    knn = 1.0 - np.sort(sims, axis=1)[:, -5:].mean(axis=1)
    return {"msp": msp, "knn": knn, "combined": (rank(msp) + rank(knn)) / 2}


def fold(held_out: str, splits: dict[str, list[Sample]], cfg: Config, cache: EmbeddingCache) -> dict:
    train = [s for s in splits["train"] if s.misconception_label != held_out]
    model = _model(cfg)
    texts = texts_of(train)
    model.tfidf.fit(texts)
    vec = response_vectors(texts, cfg.embedding.encoder, cache)
    model.clf.fit(model.design(texts, vec), [s.misconception_label for s in train])
    bank = vec[[i for i, s in enumerate(train) if s.misconception_label != NONE]]
    out = {}
    for split in ("val", "test"):
        wrong = [s for s in splits[split] if s.misconception_label != NONE]
        t = texts_of(wrong)
        v = response_vectors(t, cfg.embedding.encoder, cache)
        scores = novelty_scores(model, t, v, bank)
        unknown = np.array([s.misconception_label == held_out for s in wrong])
        preds = model.logits_from_design(model.design(t, v)).argmax(axis=1)
        confused = [model.labels[p] for p, u in zip(preds, unknown, strict=True) if u]
        out[split] = {"scores": scores, "unknown": unknown, "confused_with": confused}
    return out


def _threshold(score: np.ndarray, unknown: np.ndarray) -> float:
    known = np.sort(score[~unknown])
    return float(known[int(np.ceil((1 - TARGET_FALSE_FLAG) * len(known))) - 1])


def evaluate_open_set(splits: dict[str, list[Sample]], cfg: Config, cache: EmbeddingCache, labels: list[str]) -> dict:
    folds = {m: fold(m, splits, cfg, cache) for m in labels}
    report = {"target_false_flag_rate_on_val": TARGET_FALSE_FLAG, "scores": {}, "per_misconception": {}}
    for name in ("msp", "knn", "combined"):
        val_s = np.concatenate([f["val"]["scores"][name] for f in folds.values()])
        val_u = np.concatenate([f["val"]["unknown"] for f in folds.values()])
        thr = _threshold(val_s, val_u)
        test_s = np.concatenate([f["test"]["scores"][name] for f in folds.values()])
        test_u = np.concatenate([f["test"]["unknown"] for f in folds.values()])
        report["scores"][name] = {
            "threshold": thr,
            "val_auroc": float(roc_auc_score(val_u, val_s)),
            "test_auroc": float(roc_auc_score(test_u, test_s)),
            "test_detection_rate": float((test_s[test_u] > thr).mean()),
            "test_false_flag_rate": float((test_s[~test_u] > thr).mean()),
        }
    best = max(report["scores"], key=lambda k: report["scores"][k]["val_auroc"])
    report["selected_score"] = best
    thr = report["scores"][best]["threshold"]
    for m, f in folds.items():
        s, u = f["test"]["scores"][best], f["test"]["unknown"]
        confused = f["test"]["confused_with"]
        report["per_misconception"][m] = {
            "test_unknown_n": int(u.sum()),
            "test_auroc": float(roc_auc_score(u, s)) if 0 < u.sum() < len(u) else None,
            "detection_rate": float((s[u] > thr).mean()) if u.any() else None,
            "most_confused_with": max(set(confused), key=confused.count) if confused else None,
        }
    return report
