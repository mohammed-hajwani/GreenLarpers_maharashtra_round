class StubLLMClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, prompt: str, max_tokens: int = 400) -> str:
        self.calls += 1
        return "Let's look closely at your answer and test it against one clear case."
