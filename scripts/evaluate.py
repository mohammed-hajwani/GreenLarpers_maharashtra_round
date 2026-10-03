import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from relearn.config import load_config
from relearn.data.generator import generate_dataset
from relearn.data.splits import split_by_template
from relearn.models.artifacts import load_baseline
from relearn.models.evaluation import evaluate_model


def plot_confusion(result: dict, path: str) -> None:
    labels = result["labels"]
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.imshow(result["confusion_matrix"], cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=45)
    ax.set_yticks(range(len(labels)), labels)
    for i, row in enumerate(result["confusion_matrix"]):
        for j, v in enumerate(row):
            if v:
                ax.text(j, i, v, ha="center", va="center", fontsize=7)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title("Baseline confusion matrix, held-out templates")
    fig.tight_layout()
    fig.savefig(path, dpi=120)


def main() -> None:
    cfg = load_config()
    splits = split_by_template(generate_dataset(cfg), cfg)
    model = load_baseline(cfg.path("artifacts_dir"))
    reports = cfg.path("reports_dir")
    reports.mkdir(parents=True, exist_ok=True)
    test = evaluate_model(model, splits["test"])
    metrics = {
        "model": "baseline_tfidf_logreg",
        "temperature": model.temperature,
        "val": {k: v for k, v in evaluate_model(model, splits["val"]).items() if k != "confusion_matrix"},
        "test": test,
    }
    existing = reports / "metrics.json"
    if existing.exists():
        metrics = {**json.loads(existing.read_text(encoding="utf-8")), **metrics}
    existing.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    plot_confusion(test, str(reports / "confusion_matrix.png"))
    snapshot = {k: metrics[k] for k in metrics if k not in ("test", "val")}
    snapshot["test"] = {k: v for k, v in test.items() if k != "confusion_matrix"}
    (cfg.path("artifacts_dir") / "metrics_snapshot.json").write_text(
        json.dumps(snapshot, indent=2), encoding="utf-8"
    )
    print(
        json.dumps({"model_only": test["model_only"], "with_answer_key": test["with_answer_key"]}, indent=2)
    )


if __name__ == "__main__":
    main()
