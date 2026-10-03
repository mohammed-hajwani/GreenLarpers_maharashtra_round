import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve

from relearn.config import Config
from relearn.content import load_content
from relearn.models.base import softmax
from relearn.models.baseline import build_tfidf, texts_of
from relearn.models.embedding import EmbeddingCache, EmbeddingModel, embed, response_vectors
from relearn.models.inference import NONE, energy
from relearn.schemas import Sample

SCORES = ("msp", "energy", "knn", "definition", "combined", "energy_definition")
CURVE_POINTS = 21


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


def definition_text(misconception: str) -> list[str]:
    info = load_content().misconceptions[misconception]
    return [info.description, *info.forbidden_claims]


def definition_vectors(labels: list[str], encoder: str, cache: EmbeddingCache) -> np.ndarray:
    rows = []
    for m in labels:
        v = embed(definition_text(m), encoder, cache).mean(axis=0)
        rows.append(v / np.linalg.norm(v))
    return np.stack(rows)


def working_part(vectors: np.ndarray) -> np.ndarray:
    return vectors[:, vectors.shape[1] // 2 :]


def novelty_scores(
    model: EmbeddingModel,
    texts: list[str],
    vectors: np.ndarray,
    bank: np.ndarray,
    definitions: np.ndarray,
    temperature: float,
) -> dict[str, np.ndarray]:
    logits = model.logits_from_design(model.design(texts, vectors))
    probs = softmax(logits)
    mis = [i for i, label in enumerate(model.labels) if label != NONE]
    msp = 1.0 - probs[:, mis].max(axis=1)
    sims = (vectors @ bank.T) / 2.0
    knn = 1.0 - np.sort(sims, axis=1)[:, -5:].mean(axis=1)
    definition = 1.0 - (working_part(vectors) @ definitions.T).max(axis=1)
    e = energy(logits, temperature)
    return {
        "msp": msp,
        "energy": e,
        "knn": knn,
        "definition": definition,
        "combined": (rank(msp) + rank(knn)) / 2,
        "energy_definition": (rank(e) + rank(definition)) / 2,
    }


def zero_shot_top1(vectors: np.ndarray, all_definitions: np.ndarray, target: int) -> float:
    if not len(vectors):
        return float("nan")
    return float(((working_part(vectors) @ all_definitions.T).argmax(axis=1) == target).mean())


def fold(held_out: str, splits: dict[str, list[Sample]], cfg: Config, cache: EmbeddingCache, labels: list[str]) -> dict:
    train = [s for s in splits["train"] if s.misconception_label != held_out]
    model = _model(cfg)
    texts = texts_of(train)
    model.tfidf.fit(texts)
    vec = response_vectors(texts, cfg.embedding.encoder, cache)
    model.clf.fit(model.design(texts, vec), [s.misconception_label for s in train])
    bank = vec[[i for i, s in enumerate(train) if s.misconception_label != NONE]]
    all_defs = definition_vectors(labels, cfg.embedding.encoder, cache)
    known_defs = all_defs[[i for i, m in enumerate(labels) if m != held_out]]
    out = {}
    for split in ("val", "test"):
        wrong = [s for s in splits[split] if s.misconception_label != NONE]
        t = texts_of(wrong)
        v = response_vectors(t, cfg.embedding.encoder, cache)
        scores = novelty_scores(model, t, v, bank, known_defs, cfg.open_set.energy_temperature)
        unknown = np.array([s.misconception_label == held_out for s in wrong])
        preds = model.logits_from_design(model.design(t, v)).argmax(axis=1)
        confused = [model.labels[p] for p, u in zip(preds, unknown, strict=True) if u]
        zero_shot = zero_shot_top1(v[unknown], all_defs, labels.index(held_out))
        out[split] = {"scores": scores, "unknown": unknown, "confused_with": confused, "zero_shot_top1": zero_shot}
    return out


def _threshold(score: np.ndarray, unknown: np.ndarray, target: float) -> float:
    known = np.sort(score[~unknown])
    return float(known[int(np.ceil((1 - target) * len(known))) - 1])


def _curve(unknown: np.ndarray, score: np.ndarray) -> dict:
    fpr, tpr, _ = roc_curve(unknown, score)
    grid = np.linspace(0.0, 1.0, CURVE_POINTS)
    return {"false_flag_rate": grid.round(3).tolist(), "detection_rate": np.interp(grid, fpr, tpr).round(4).tolist()}


def evaluate_open_set(splits: dict[str, list[Sample]], cfg: Config, cache: EmbeddingCache, labels: list[str]) -> dict:
    target = cfg.open_set.target_false_flag
    folds = {m: fold(m, splits, cfg, cache, labels) for m in labels}
    report = {
        "target_false_flag_rate_on_val": target,
        "energy_temperature": cfg.open_set.energy_temperature,
        "runtime_scores": list(cfg.open_set.runtime_scores),
        "scores": {},
        "curves": {},
        "per_misconception": {},
    }
    for name in SCORES:
        val_s = np.concatenate([f["val"]["scores"][name] for f in folds.values()])
        val_u = np.concatenate([f["val"]["unknown"] for f in folds.values()])
        thr = _threshold(val_s, val_u, target)
        test_s = np.concatenate([f["test"]["scores"][name] for f in folds.values()])
        test_u = np.concatenate([f["test"]["unknown"] for f in folds.values()])
        report["scores"][name] = {
            "threshold": thr,
            "val_auroc": float(roc_auc_score(val_u, val_s)),
            "test_auroc": float(roc_auc_score(test_u, test_s)),
            "test_detection_rate": float((test_s[test_u] > thr).mean()),
            "test_false_flag_rate": float((test_s[~test_u] > thr).mean()),
        }
        report["curves"][name] = _curve(test_u, test_s)
    usable = [k for k in report["scores"] if k in cfg.open_set.runtime_scores]
    best = max(usable, key=lambda k: report["scores"][k]["val_auroc"])
    report["selected_score"] = best
    thr = report["scores"][best]["threshold"]
    for m, f in folds.items():
        u, confused = f["test"]["unknown"], f["test"]["confused_with"]
        row = {"test_unknown_n": int(u.sum())}
        for name in SCORES:
            s = f["test"]["scores"][name]
            row[f"{name}_auroc"] = float(roc_auc_score(u, s)) if 0 < u.sum() < len(u) else None
        s = f["test"]["scores"][best]
        row["test_auroc"] = row[f"{best}_auroc"]
        row["detection_rate"] = float((s[u] > thr).mean()) if u.any() else None
        row["most_confused_with"] = max(set(confused), key=confused.count) if confused else None
        row["zero_shot_top1"] = f["test"]["zero_shot_top1"]
        report["per_misconception"][m] = row
    return report
