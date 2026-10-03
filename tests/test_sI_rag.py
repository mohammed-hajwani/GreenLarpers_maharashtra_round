from relearn.content import load_content
from relearn.intervention.checker import check_intervention
from relearn.intervention.grounded import build_grounded_intervention
from relearn.learner.store import LearnerStore
from relearn.llm.anthropic_client import make_llm
from relearn.llm.stub import StubLLMClient
from relearn.pipeline import Tutor
from relearn.rag.retriever import build_corpus, get_retriever
from relearn.schemas import LearnerResponse

RESPONSE = LearnerResponse(question_id="q", answer="2.7 N", working="The force from the hit keeps it moving forward.")
CONCEPT = load_content().misconceptions["M01"].correct_concept


class FakeLLM:
    def __init__(self, text: str | None = None, fail: bool = False) -> None:
        self.text, self.fail, self.prompts = text, fail, []

    def complete(self, system: str, prompt: str, max_tokens: int = 400) -> str:
        self.prompts.append(prompt)
        if self.fail:
            raise TimeoutError("simulated timeout")
        return self.text


def _passages():
    return get_retriever().retrieve("needs a force to keep moving", "M01")


def test_corpus_and_retrieval() -> None:
    corpus = build_corpus()
    assert {p.source for p in corpus} == {"misconceptions.yaml", "interventions.yaml", "item_bank.yaml"}
    hits = _passages()
    assert len(hits) == 3 and all(-1 <= h["cosine"] <= 1 for h in hits)
    concept = load_content().concept_of("M01")
    assert all(load_content().concept_of(h["passage_id"].split(":")[0]) == concept for h in hits)


def test_grounded_llm_path_validated() -> None:
    llm = FakeLLM(f"You wrote that the hit keeps pushing the ball, but nothing touches it after the kick. {CONCEPT}")
    iv, mode = build_grounded_intervention("M01", "counterexample", RESPONSE, llm, _passages(), 0.3)
    assert mode == "llm_grounded" and check_intervention(iv)
    assert "Passages:" in llm.prompts[0] and "30%" in llm.prompts[0]


def test_invalid_llm_output_falls_back() -> None:
    bad = FakeLLM("Yes, it needs a force to keep moving. " + CONCEPT)
    iv, mode = build_grounded_intervention("M01", "counterexample", RESPONSE, bad, _passages())
    assert mode == "template_with_retrieval" and check_intervention(iv)
    missing = FakeLLM("A short answer without the concept sentence.")
    assert (
        build_grounded_intervention("M01", "counterexample", RESPONSE, missing, _passages())[1]
        == "template_with_retrieval"
    )


def test_llm_error_falls_back() -> None:
    iv, mode = build_grounded_intervention("M01", "counterexample", RESPONSE, FakeLLM(fail=True), _passages())
    assert mode == "template_with_retrieval" and check_intervention(iv)


def test_no_key_uses_stub(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(make_llm(), StubLLMClient)


def test_pipeline_records_sources(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "i.db"))
    iv = tutor.intervene("L", "M01", RESPONSE)
    assert iv.mode == "template_with_retrieval" and iv.sources
    logged = [e for e in tutor.store.timeline("L") if e["kind"] == "intervention"][-1]
    assert logged["sources"] == [s["passage_id"] for s in iv.sources]
