import json
import statistics

from relearn.config import load_config
from relearn.data.pipeline import build_splits
from relearn.diagnosis.probe_eval import compare_probing
from relearn.models.registry import BASELINE, EMBEDDING, load_model

SEEDS = [42, 43, 44, 45, 46]
STRATEGIES = ("no_probe", "random_probe", "information_gain_probe")


def summarize(runs: list[dict]) -> dict:
    out = {"n": runs[0]["n"], "routed_to_probe": runs[0]["routed_to_probe"], "seeds": SEEDS}
    for name in STRATEGIES:
        acc = [r[name]["accuracy"] for r in runs]
        out[name] = {
            "accuracy_mean": statistics.mean(acc),
            "accuracy_std": statistics.pstdev(acc),
            "probes_asked_mean": statistics.mean(r[name]["probes_asked"] for r in runs),
            "entropy_drop_bits_per_probe_mean": statistics.mean(
                r[name]["mean_entropy_drop_bits_per_probe"] for r in runs
            ),
        }
    base = out["no_probe"]["accuracy_mean"]
    for name in STRATEGIES[1:]:
        out[name]["lift_points"] = 100 * (out[name]["accuracy_mean"] - base)
    out["information_gain_beats_random"] = (
        out["information_gain_probe"]["accuracy_mean"] > out["random_probe"]["accuracy_mean"]
    )
    return out


def probing_report() -> dict:
    cfg = load_config()
    splits = build_splits(cfg)
    report = {
        "method": "simulated learners hold the sample's true misconception and answer each probe with "
        f"the stored expected option, with answer noise {cfg.disambiguation.answer_noise}",
        "subset": "confusable-group samples",
        "results": {},
    }
    for kind in (EMBEDDING, BASELINE):
        model = load_model(kind)
        report["results"][kind] = {
            split: summarize([compare_probing(splits[split], model, seed) for seed in SEEDS])
            for split in ("val", "test")
        }
    return report


def main() -> None:
    path = load_config().path("reports_dir") / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    metrics["probing"] = probing_report()
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    for kind, splits in metrics["probing"]["results"].items():
        for split, r in splits.items():
            print(
                kind,
                split,
                " ".join(f"{s}={r[s]['accuracy_mean']:.3f}" for s in STRATEGIES),
                "ig>random" if r["information_gain_beats_random"] else "ig<=random",
            )


if __name__ == "__main__":
    main()
