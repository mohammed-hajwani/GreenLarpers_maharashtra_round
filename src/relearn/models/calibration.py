import numpy as np

TEMPERATURE_GRID = np.round(np.arange(0.1, 5.01, 0.05), 2)
ECE_BINS = 10


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(logits: np.ndarray, targets: np.ndarray, temperature: float) -> float:
    p = _softmax(logits / temperature)
    return float(-np.mean(np.log(p[np.arange(len(targets)), targets] + 1e-12)))


def fit_temperature_from_logits(logits: np.ndarray, targets: np.ndarray) -> float:
    scores = [nll(logits, targets, float(t)) for t in TEMPERATURE_GRID]
    return float(TEMPERATURE_GRID[int(np.argmin(scores))])


def expected_calibration_error(probs: np.ndarray, targets: np.ndarray) -> float:
    conf = probs.max(axis=1)
    correct = probs.argmax(axis=1) == targets
    edges = np.linspace(0, 1, ECE_BINS + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)
