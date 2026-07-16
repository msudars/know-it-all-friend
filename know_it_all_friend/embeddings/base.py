"""Embedding backend interface (Phase 6)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """Interface for embedding backends.

    ``model`` identifies the embedding model; it is recorded in the vector
    index so queries are always embedded with the same model that built it.
    """

    model: str

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Return the embedding vector for a single query string."""
        return self.embed_texts([text])[0]
