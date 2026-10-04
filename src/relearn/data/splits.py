from relearn.config import Config
from relearn.content import load_content
from relearn.schemas import Sample


def template_splits(cfg: Config) -> dict[str, str]:
    content = load_content()
    n_val = cfg.data.val_templates_per_misconception
    n_test = cfg.data.test_templates_per_misconception
    assignment: dict[str, str] = {}
    for m in sorted(content.misconceptions):
        ids = sorted(t.template_id for t in content.templates if t.primary == m)
        for i, template_id in enumerate(ids):
            if i >= len(ids) - n_test:
                assignment[template_id] = "test"
            elif i >= len(ids) - n_test - n_val:
                assignment[template_id] = "val"
            else:
                assignment[template_id] = "train"
    return assignment


def split_by_template(samples: list[Sample], cfg: Config) -> dict[str, list[Sample]]:
    assignment = template_splits(cfg)
    out: dict[str, list[Sample]] = {"train": [], "val": [], "test": []}
    for s in samples:
        out[assignment[s.question.template_id]].append(s)
    return out
