import json

from relearn.config import load_config
from relearn.multimodal.sim_eval import compare


def main() -> None:
    report = compare()
    path = load_config().path("reports_dir") / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    metrics["modality_simulation"] = report
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    for policy, r in report["results"].items():
        print(
            f"{policy:<15} first-try {r['first_try_resolution']['mean']:.3f}  "
            f"first-try (last third) {r['first_try_resolution_last_third']['mean']:.3f}  "
            f"within 3 {r['resolved_within_3']['mean']:.3f}  interventions {r['mean_interventions']['mean']:.2f}"
        )


if __name__ == "__main__":
    main()
