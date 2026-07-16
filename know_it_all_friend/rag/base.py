"""LLM backend interface (Phase 9)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator


class BaseLLM(ABC):
    """Interface for answer-generating LLM backends."""

    model: str

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        """Return the model's response to ``prompt``."""
        ...

    def generate_stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        """Yield the answer incrementally. Backends that can't stream fall back to one chunk."""
        yield self.generate(prompt, system=system)
