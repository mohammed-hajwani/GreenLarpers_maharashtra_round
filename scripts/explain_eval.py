import json

from relearn.config import load_config
from relearn.learning.explain import evaluate_explanations
from relearn.models.loader import get_active_model


def main() -> None:
    report = evaluate_explanations(get_active_model().model)
    path = load_config().path("reports_dir") / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    metrics["explain_back"] = report
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))
    for d in report["details"]:
        print(d["misconception"], "holds" if d["holds"] else "sound", d["status"], d["probability"])


if __name__ == "__main__":
    main()
