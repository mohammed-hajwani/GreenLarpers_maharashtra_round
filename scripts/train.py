import numpy as np

from relearn.config import load_config
from relearn.data.generator import generate_dataset
from relearn.data.splits import split_by_template
from relearn.models.artifacts import save_baseline
from relearn.models.baseline import texts_of, train_baseline
from relearn.models.calibration import fit_temperature_from_logits


def main() -> None:
    cfg = load_config()
    splits = split_by_template(generate_dataset(cfg), cfg)
    model = train_baseline(splits["train"], cfg)
    val = splits["val"]
    targets = np.array([model.labels.index(s.misconception_label) for s in val])
    model.temperature = fit_temperature_from_logits(model.logits(texts_of(val)), targets)
    save_baseline(model, cfg.path("artifacts_dir"))
    print(f"baseline saved, temperature={model.temperature}")


if __name__ == "__main__":
    main()
