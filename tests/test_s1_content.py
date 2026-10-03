from collections import Counter

from relearn.content import ALLOWED_STRATEGIES, load_content

MIN_TEMPLATES = 4


def test_taxonomy() -> None:
    c = load_content()
    assert len(c.misconceptions) == 12
    assert len(c.labels()) == 13
    for group, members in c.confusable_groups.items():
        for m in members:
            assert c.misconceptions[m].confusable_group == group


def test_templates_per_misconception() -> None:
    c = load_content()
    ids = [t.template_id for t in c.templates]
    assert len(ids) == len(set(ids))
    by_primary: dict[str, set] = {}
    for t in c.templates:
        assert t.primary in c.misconceptions
        assert t.primary in t.wrong
        for label in t.wrong:
            assert label in c.misconceptions
        by_primary.setdefault(t.primary, set()).add(t.question_type)
    for m in c.misconceptions:
        assert sum(t.primary == m for t in c.templates) >= MIN_TEMPLATES
        assert len(by_primary[m]) == 3


def test_confusable_templates_cover_groups() -> None:
    c = load_content()
    for group, members in c.confusable_groups.items():
        multi = [t for t in c.templates if t.confusable_group == group and len(set(t.wrong) & set(members)) >= 2]
        assert multi, group


def test_probes() -> None:
    c = load_content()
    counts = Counter(p.confusable_group for p in c.probes)
    for group in c.confusable_groups:
        assert counts[group] >= 3
    for p in c.probes:
        for label in c.confusable_groups[p.confusable_group]:
            assert p.expected_answer_by_label[label] in p.options


def test_interventions() -> None:
    c = load_content()
    for m in c.misconceptions:
        strategies = c.interventions[m]
        assert len(strategies) >= 3
        for s in strategies:
            assert s.strategy in ALLOWED_STRATEGIES
            assert "{correct_concept}" in s.template


def test_item_bank() -> None:
    c = load_content()
    for m in c.misconceptions:
        kinds = Counter(i.kind for i in c.items if i.misconception == m)
        assert kinds["transfer"] >= 3
        assert kinds["trap"] >= 1
        assert kinds["retest"] >= 1
    for i in c.items:
        assert i.correct_answer in i.options
        for option, label in i.trap_answer_maps_to.items():
            assert option in i.options
            assert label == i.misconception
        if i.kind == "trap":
            assert i.trap_answer_maps_to
