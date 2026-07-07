"""LLM backend interface (Phase 9)."""

from __future__ import annotations


class BaseLLM:
    """Interface for answer-generating LLM backends."""

    model: str

    def generate(self, prompt: str, system: str | None = None) -> str:
        """Return the model's response to ``prompt``."""
        raise NotImplementedError
