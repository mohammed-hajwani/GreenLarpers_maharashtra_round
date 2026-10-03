import os

DEFAULT_MODEL = "claude-opus-5-5"
TIMEOUT_SECONDS = 5.0


class LLMUnavailable(RuntimeError):
    pass


class AnthropicClient:
    def __init__(self, model: str | None = None, timeout: float = TIMEOUT_SECONDS) -> None:
        import anthropic

        self.anthropic = anthropic
        self.model = model or os.environ.get("RELEARN_LLM_MODEL", DEFAULT_MODEL)
        self.client = anthropic.Anthropic(timeout=timeout, max_retries=0)

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        a = self.anthropic
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": prompt}],
            )
        except (a.APITimeoutError, a.APIConnectionError, a.RateLimitError, a.APIStatusError) as exc:
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if response.stop_reason == "refusal":
            raise LLMUnavailable("refusal")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise LLMUnavailable("empty response")
        return text


def make_llm():
    from relearn.llm.stub import StubLLMClient

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return StubLLMClient()
    try:
        return AnthropicClient()
    except Exception:
        return StubLLMClient()
