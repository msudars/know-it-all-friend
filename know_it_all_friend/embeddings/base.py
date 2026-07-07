"""Embedding backend interface (Phase 6)."""

from __future__ import annotations


class BaseEmbedder:
    """Interface for embedding backends.

    ``model`` identifies the embedding model; it is recorded in the vector
    index so queries are always embedded with the same model that built it.
    """

    model: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        """Return the embedding vector for a single query string."""
        return self.embed_texts([text])[0]
