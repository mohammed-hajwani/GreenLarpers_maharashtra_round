from dataclasses import asdict, dataclass, field

from relearn.config import load_config
from relearn.schemas import Diagnosis


@dataclass
class MasteryState:
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)


@dataclass
class MasteryUpdate:
    concept: str
    event: str
    ref_id: str
    alpha_before: float
    beta_before: float
    alpha_after: float
    beta_after: float
    detail: dict = field(default_factory=dict)

    @property
    def before(self) -> float:
        return self.alpha_before / (self.alpha_before + self.beta_before)

    @property
    def after(self) -> float:
        return self.alpha_after / (self.alpha_after + self.beta_after)

    def to_dict(self) -> dict:
        return {**asdict(self), "before": self.before, "after": self.after}


def prior() -> MasteryState:
    m = load_config().mastery
    return MasteryState(m.prior_alpha, m.prior_beta)


def apply(state: MasteryState, d_alpha: float, d_beta: float) -> MasteryState:
    m = load_config().mastery
    alpha = m.prior_alpha + m.decay * (state.alpha - m.prior_alpha) + d_alpha
    beta = m.prior_beta + m.decay * (state.beta - m.prior_beta) + d_beta
    return MasteryState(alpha, beta)


def practice_evidence(correct: bool, difficulty: str, diagnosis: Diagnosis | None) -> tuple[float, float, dict]:
    m = load_config().mastery
    weight = m.difficulty_weight.get(difficulty, 1.0)
    if correct:
        return m.correct * weight, 0.0, {"difficulty": difficulty, "weight": weight, "correct": True}
    confidence = 0.0
    label = None
    if diagnosis is not None and not diagnosis.is_correct:
        label, confidence = diagnosis.top_labels[0]
    return (
        0.0,
        m.wrong + m.misconception_weight * confidence,
        {"difficulty": difficulty, "misconception": label, "confidence": confidence, "correct": False},
    )


def probe_evidence(answer_matches_misconception: bool, answer_matches_correct: bool) -> tuple[float, float, dict]:
    m = load_config().mastery
    if answer_matches_correct:
        return m.probe, 0.0, {"probe_signal": "correct_concept"}
    if answer_matches_misconception:
        return 0.0, m.probe, {"probe_signal": "consistent_with_misconception"}
    return 0.0, 0.0, {"probe_signal": "uninformative"}


def item_evidence(kind: str, correct: bool) -> tuple[float, float, dict]:
    m = load_config().mastery
    table = {
        "transfer": (m.transfer_correct, m.transfer_wrong),
        "trap": (m.trap_pass, m.trap_fail),
        "retest": (m.retest_pass, m.retest_fail),
    }
    up, down = table[kind]
    return (
        (up, 0.0, {"item_kind": kind, "correct": True})
        if correct
        else (0.0, down, {"item_kind": kind, "correct": False})
    )


def update(
    state: MasteryState, concept: str, event: str, ref_id: str, evidence: tuple[float, float, dict]
) -> tuple[MasteryState, MasteryUpdate]:
    d_alpha, d_beta, detail = evidence
    after = apply(state, d_alpha, d_beta)
    record = MasteryUpdate(concept, event, ref_id, state.alpha, state.beta, after.alpha, after.beta, detail)
    return after, record
