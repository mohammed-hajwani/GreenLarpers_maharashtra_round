import json

from relearn.config import load_config
from relearn.progress.model import train


def main() -> None:
    meta = train()
    path = load_config().path("reports_dir") / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    metrics["progress_model"] = {
        "label": meta["label"],
        "metrics": meta["metrics"],
        "assumptions": meta["training_dataset"]["assumptions"],
    }
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    for target, r in meta["metrics"].items():
        print(target, r["model"], {k: round(v, 3) for k, v in r["test"].items()})


if __name__ == "__main__":
    main()
