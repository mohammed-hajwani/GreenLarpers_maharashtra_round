from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system: str, prompt: str, max_tokens: int = 400) -> str: ...
