import re

from relearn.models.base import TextClassifier
from relearn.models.baseline import sample_text
from relearn.models.embedding import EmbeddingModel
from relearn.schemas import LearnerResponse, Question

WORD = re.compile(r"\S+")
MAX_OCCLUSION_WORDS = 40


def occlusion(model: TextClassifier, question: Question, response: LearnerResponse, label: str, k: int = 5) -> list:
    words = WORD.findall(response.working)[:MAX_OCCLUSION_WORDS]
    if not words or label not in model.labels:
        return []
    idx = model.labels.index(label)
    variants = [
        sample_text(question, response.model_copy(update={"working": " ".join(words[:i] + words[i + 1 :])}))
        for i in range(len(words))
    ]
    full = sample_text(question, response.model_copy(update={"working": " ".join(words)}))
    probs = model.predict_proba([full] + variants)[:, idx]
    deltas = [(words[i], float(probs[0] - probs[i + 1])) for i in range(len(words))]
    return sorted(deltas, key=lambda x: -x[1])[:k]


def explain(model: TextClassifier, question: Question, response: LearnerResponse, label: str) -> dict:
    text = sample_text(question, response)
    out = {"label": label, "model_name": model.name, "methods": []}
    features = model.top_features(text, label) if hasattr(model, "top_features") else []
    if features:
        out["methods"].append("tfidf_coefficients")
        out["influential_features"] = [{"feature": f, "contribution": round(c, 4)} for f, c in features]
    if isinstance(model, EmbeddingModel):
        out["methods"].append("nearest_training_examples")
        out["similar_examples"] = [{"text": t, "cosine": round(s, 4)} for t, s in model.similar_examples(text, label)]
        out["methods"].append("token_occlusion")
        out["occlusion"] = [
            {"word": w, "probability_drop": round(d, 4)} for w, d in occlusion(model, question, response, label)
        ]
    return out
