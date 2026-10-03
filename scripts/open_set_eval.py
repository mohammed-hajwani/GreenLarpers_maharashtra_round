import json

from relearn.config import load_config
from relearn.content import load_content
from relearn.data.pipeline import build_splits
from relearn.models.embedding import EmbeddingCache
from relearn.models.open_set import evaluate_open_set


def main() -> None:
    cfg = load_config()
    splits = build_splits(cfg)
    cache = EmbeddingCache(cfg.path("data_dir") / "embedding_cache.npz")
    report = evaluate_open_set(splits, cfg, cache, sorted(load_content().misconceptions))
    cache.save()
    import yaml

    from relearn.diagnosis.routing import THRESHOLDS_PATH

    data = yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    chosen = report["scores"][report["selected_score"]]
    data["open_set"] = {"score": report["selected_score"], "threshold": round(chosen["threshold"], 4), "split": "val"}
    THRESHOLDS_PATH.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    path = cfg.path("reports_dir") / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    metrics["open_set"] = report
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    for name, r in report["scores"].items():
        print(name, {k: round(v, 3) for k, v in r.items()})
    print("selected", report["selected_score"])
    for m, r in report["per_misconception"].items():
        print(m, r)


if __name__ == "__main__":
    main()
