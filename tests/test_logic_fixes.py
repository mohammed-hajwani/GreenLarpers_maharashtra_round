import numpy as np
import pytest

from relearn.adaptive import difficulty
from relearn.assessment.planner import plan_assessment, plan_retest
from relearn.config import load_config
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.diagnosis.diagnoser import diagnose
from relearn.diagnosis.disambiguator import bayes_update, choose_probe
from relearn.intervention.checker import QUOTED, check_intervention
from relearn.learner.mastery import MasteryState, apply
from relearn.learner.state import new_record, on_intervention
from relearn.learner.store import LearnerStore
from relearn.models.base import TextClassifier
from relearn.pipeline import Tutor
from relearn.schemas import Intervention, LearnerResponse, MisconceptionState, QuestionType


class FixedModel(TextClassifier):
    name = "fixed"

    def __init__(self, scores: dict[str, float]) -> None:
        self._labels = ["none", *sorted(load_content().misconceptions)]
        self.scores = scores

    @property
    def labels(self) -> list[str]:
        return self._labels

    def logits(self, texts: list[str]) -> np.ndarray:
        row = np.log(np.array([self.scores.get(label, 1e-4) for label in self._labels]))
        return np.tile(row, (len(texts), 1))


def _mcq(misconception: str):
    content = load_content()
    t = next(t for t in content.templates if t.primary == misconception and t.question_type == QuestionType.mcq)
    return make_question(t, {k: v[0] for k, v in t.params.items()})


def test_retest_pass_while_still_intervened_reschedules(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "s.db"))
    record = on_intervention(new_record("L", "M01"), "counterexample")
    record.alpha = 40.0
    tutor.store.put(record, 0)
    item = plan_retest("M01")
    _, after = tutor.submit_retest("L", item, item.correct_answer)
    assert after.state == MisconceptionState.intervened
    gap = load_config().assessment.retest_gap
    assert tutor.store.retest_due("L", "M01") == tutor.store.attempt_count("L") + gap


def test_retest_pass_that_resolves_clears_schedule(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "s.db"))
    record = on_intervention(new_record("L", "M01"), "counterexample")
    record.beta = 6.0
    tutor.store.put(record, 0)
    item = plan_retest("M01")
    _, after = tutor.submit_retest("L", item, item.correct_answer)
    assert after.state == MisconceptionState.resolved
    assert tutor.store.retest_due("L", "M01") is None


def test_correct_option_with_flawed_working_is_probed() -> None:
    question = _mcq("M01")
    response = LearnerResponse(question_id=question.question_id, answer=question.correct_answer, working="x")
    d = diagnose(question, response, FixedModel({"M01": 0.9, "none": 0.05}))
    assert not d.is_correct and d.needs_probing and d.route == "probe"
    assert d.posterior["M01"] > 0.7
    assert choose_probe(d) is not None


def test_correct_option_with_sound_working_still_uses_answer_key() -> None:
    question = _mcq("M01")
    response = LearnerResponse(question_id=question.question_id, answer=question.correct_answer, working="x")
    d = diagnose(question, response, FixedModel({"M01": 0.5, "none": 0.4}))
    assert d.is_correct and not d.needs_probing
    assert d.posterior["none"] == pytest.approx(1.0)


def test_probe_can_revive_zero_none() -> None:
    probe = next(p for p in load_content().probes if "none" in p.expected_answer_by_label)
    posterior = {label: 0.0 for label in probe.expected_answer_by_label}
    first = next(label for label in probe.expected_answer_by_label if label != "none")
    posterior[first] = 1.0
    updated = bayes_update(posterior, probe, probe.expected_answer_by_label["none"])
    assert updated["none"] > 0.0


def test_battery_decays_once_per_concept(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "s.db"))
    items = plan_assessment("M01")
    answers = {i.item_id: i.correct_answer for i in items}
    tutor.store.put(on_intervention(new_record("L", "M01"), "counterexample"))
    tutor.submit_assessment("L", "M01", items, answers)
    updates = tutor.last_trace["mastery_updates"]
    assert [u["detail"]["decayed"] for u in updates] == [True, False, False, False]


def test_apply_without_decay_keeps_counts() -> None:
    state = MasteryState(5.0, 3.0)
    assert apply(state, 1.0, 0.0, decay=False) == MasteryState(6.0, 3.0)
    assert apply(state, 1.0, 0.0).alpha < 6.0


def test_curly_and_single_quotes_are_treated_as_quotes() -> None:
    assert QUOTED.sub("", "you said “it needs a force” earlier") == "you said  earlier"
    assert QUOTED.sub("", "you said 'it needs a force' earlier") == "you said  earlier"
    assert QUOTED.sub("", "it's fine") == "it's fine"
    info = load_content().misconceptions["M01"]
    claim = info.forbidden_claims[0]
    text = f"You wrote “{claim}”. {info.correct_concept}"
    assert check_intervention(Intervention(misconception="M01", strategy="x", text=text, follow_up_prompt="?"))


def test_pick_template_falls_back_when_concept_has_no_templates() -> None:
    template, gap = difficulty.pick_template("no_such_concept", "medium", [])
    assert template in load_content().templates
    assert "fell back" in gap
