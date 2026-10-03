import json

from relearn.config import load_config
from relearn.data.generator import generate_dataset
from relearn.data.splits import split_by_template
from relearn.data.validate import dataset_stats, validate_dataset


def main() -> None:
    cfg = load_config()
    samples = generate_dataset(cfg)
    splits = split_by_template(samples, cfg)
    errors = validate_dataset(samples, splits, cfg)
    if errors:
        raise SystemExit("validation failed: " + "; ".join(errors[:10]))
    out = cfg.path("data_dir")
    out.mkdir(parents=True, exist_ok=True)
    for name, items in splits.items():
        with (out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for s in items:
                handle.write(s.model_dump_json() + "\n")
    stats = dataset_stats(samples)
    stats["splits"] = {k: len(v) for k, v in splits.items()}
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
