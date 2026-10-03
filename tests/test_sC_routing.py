from relearn.config import load_config
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.diagnosis.diagnoser import diagnose, entropy_bits, finalize
from relearn.diagnosis.routing import ACCEPT, PROBE, UNCERTAIN, route_for, thresholds_for
from relearn.models.loader import get_active_model
from relearn.schemas import LearnerResponse

T = {"accept": 0.8, "probe": 0.5}


def test_route_bands() -> None:
    assert route_for(0.95, T) == ACCEPT
    assert route_for(0.80, T) == ACCEPT
    assert route_for(0.79, T) == PROBE
    assert route_for(0.50, T) == PROBE
    assert route_for(0.49, T) == UNCERTAIN


def test_thresholds_from_config() -> None:
    defaults = thresholds_for(None)
    assert defaults == {"accept": 0.8, "probe": 0.5}
    tuned = thresholds_for("v1_embedding")
    assert 0.5 < tuned["accept"] <= 0.95 and tuned["probe"] == 0.5


def test_finalize_routes() -> None:
    assert finalize({"M01": 0.9, "M09": 0.1}).route == ACCEPT
    d = finalize({"M01": 0.6, "M09": 0.4})
    assert d.route == PROBE and d.ambiguous
    assert finalize({"M01": 0.4, "M02": 0.35, "M03": 0.25}).route == UNCERTAIN
    assert finalize({"none": 0.6, "M01": 0.4}).route == ACCEPT


def test_entropy() -> None:
    assert abs(entropy_bits({"a": 0.5, "b": 0.5}) - 1.0) < 1e-9
    assert entropy_bits({"a": 1.0}) == 0.0


def test_diagnosis_carries_model_info() -> None:
    t = next(t for t in load_content().templates if t.template_id == "m01_puck_ice_01")
    q = make_question(t, {"m": 0.5, "v": 8})
    d = diagnose(
        q, LearnerResponse(question_id=q.question_id, answer="4.0 N forward", working="it needs a force")
    )
    active = get_active_model().model
    assert d.model_name == active.name and d.model_version == active.version
    assert abs(sum(d.posterior.values()) - 1.0) < 1e-6
    assert d.confidence == d.top_labels[0][1]
    assert len(d.top_labels) == load_config().diagnosis.top_k
