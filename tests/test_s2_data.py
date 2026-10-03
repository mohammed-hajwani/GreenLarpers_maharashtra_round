from relearn.config import load_config
from relearn.data.generator import generate_dataset
from relearn.data.render import render
from relearn.data.splits import split_by_template
from relearn.data.validate import dataset_stats, validate_dataset

MIN_PER_GROUP = 150


def test_render() -> None:
    assert render("{m*9.8:.1f} N", {"m": 2}) == "19.6 N"
    assert render("{m} kg", {"m": 2.0}) == "2 kg"
    assert render("{m*9.8*cosd(theta):.1f}", {"m": 1, "theta": 0}) == "9.8"


def test_dataset_gate() -> None:
    cfg = load_config()
    samples = generate_dataset(cfg)
    splits = split_by_template(samples, cfg)
    assert validate_dataset(samples, splits, cfg) == []
    stats = dataset_stats(samples)
    assert stats["total"] >= cfg.data.min_total_samples
    assert stats["imbalance"] <= cfg.data.max_class_imbalance
    for group in ["CG1", "CG2", "CG3", "CG4"]:
        assert stats["confusable_groups"][group] >= MIN_PER_GROUP
    train_templates = {s.question.template_id for s in splits["train"]}
    test_templates = {s.question.template_id for s in splits["test"]}
    assert not train_templates & test_templates


def test_deterministic() -> None:
    cfg = load_config()
    a = generate_dataset(cfg)
    b = generate_dataset(cfg)
    assert [s.model_dump() for s in a[:50]] == [s.model_dump() for s in b[:50]]
