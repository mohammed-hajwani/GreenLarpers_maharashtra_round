import numpy as np


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class TextClassifier:
    name: str = "classifier"
    version: str = "0"
    temperature: float = 1.0
    kind: str | None = None

    @property
    def labels(self) -> list[str]:
        raise NotImplementedError

    def logits(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError

    def predict_proba(self, texts: list[str], calibrated: bool = True) -> np.ndarray:
        t = self.temperature if calibrated else 1.0
        return softmax(self.logits(texts) / t)

    def predict(self, texts: list[str]) -> list[str]:
        return [self.labels[i] for i in self.predict_proba(texts).argmax(axis=1)]
