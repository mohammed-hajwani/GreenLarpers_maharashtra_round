import json
from datetime import UTC, datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from relearn.adaptive.difficulty import coverage_report
from relearn.config import load_config
from relearn.data.handwritten import load_handwritten
from relearn.data.pipeline import build_splits
from relearn.models.evaluation import evaluate_model
from relearn.models.registry import BASELINE, EMBEDDING, load_model, read_metadata, update_metadata


def plot_confusion(result: dict, title: str, path: str) -> None:
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
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    cfg = load_config()
    splits = build_splits(cfg)
    handwritten = load_handwritten()
    reports = cfg.path("reports_dir")
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / "metrics.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    models = {}
    for kind in (BASELINE, EMBEDDING):
        model = load_model(kind)
        meta = read_metadata(kind)
        result = {
            "name": model.name,
            "version": model.version,
            "training_date": meta.get("training_date"),
            "temperature": model.temperature,
            "val": evaluate_model(model, splits["val"]),
            "test": evaluate_model(model, splits["test"]),
            "handwritten": evaluate_model(model, handwritten),
        }
        plot_confusion(
            result["test"], f"{kind} test (held-out templates)", str(reports / f"confusion_{kind}_test.png")
        )
        plot_confusion(
            result["handwritten"],
            f"{kind} hand-written set",
            str(reports / f"confusion_{kind}_handwritten.png"),
        )
        update_metadata(
            kind,
            metrics={
                split: {k: result[split][k] for k in ("model_only", "with_answer_key", "ece_calibrated")}
                for split in ("val", "test", "handwritten")
            },
        )
        models[kind] = result
    comparison = [
        {
            "model": kind,
            "eval_set": split,
            "mode": mode,
            **{
                k: models[kind][split][mode][k]
                for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1")
            },
        }
        for kind in models
        for split in ("test", "handwritten")
        for mode in ("model_only", "with_answer_key")
    ]
    metrics = {
        **{k: v for k, v in previous.items() if k in ("probing", "simulation", "progress_model")},
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_provenance": "synthetic",
        "dataset": {
            "total": sum(len(v) for v in splits.values()),
            "split_sizes": {k: len(v) for k, v in splits.items()},
            "split_method": "by question template; test templates never appear in train or val",
            "handwritten_test_size": len(handwritten),
            "handwritten_provenance": "hand-written by the project team, not real student data",
        },
        "difficulty_coverage": coverage_report(),
        "comparison": comparison,
        "models": models,
    }
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    for row in comparison:
        print(
            f"{row['model']:<13} {row['eval_set']:<11} {row['mode']:<16} "
            f"acc={row['accuracy']:.3f} macroF1={row['macro_f1']:.3f}"
        )


if __name__ == "__main__":
    main()
