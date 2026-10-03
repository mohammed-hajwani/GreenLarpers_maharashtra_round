import json

from relearn.config import load_config
from relearn.data.pipeline import build_splits
from relearn.models.embedding import EmbeddingCache
from relearn.models.registry import BASELINE, EMBEDDING, read_metadata
from relearn.models.training import train_baseline_versioned, train_embedding_versioned


def main() -> None:
    cfg = load_config()
    splits = build_splits(cfg)
    train_baseline_versioned(splits, cfg)
    cache = EmbeddingCache(cfg.path("data_dir") / "embedding_cache.npz")
    train_embedding_versioned(splits, cfg, cache)
    cache.save()
    for kind in (BASELINE, EMBEDDING):
        meta = read_metadata(kind)
        print(
            kind,
            json.dumps({k: meta.get(k) for k in ("val_macro_f1", "calibration", "candidate_val_macro_f1")}),
        )


if __name__ == "__main__":
    main()
