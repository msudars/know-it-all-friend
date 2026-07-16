"""Ollama-backed embedding backend: local-first, no data leaves the machine."""

from __future__ import annotations

import logging
import typing

from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.retry import with_retry

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL = "nomic-embed-text"

# Ollama accepts a list per request, but very large batches risk timeouts on
# modest hardware; embedding in slices keeps memory and request size bounded.
_BATCH_SIZE = 32


class OllamaEmbedder(BaseEmbedder):
    def __init__(self, model: str = DEFAULT_EMBED_MODEL, host: str | None = None):
        import ollama

        self.model = model
        self._client = ollama.Client(host=host)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start : start + _BATCH_SIZE]
            def _call() -> typing.Any:
                return self._client.embed(model=self.model, input=batch)
            
            response = with_retry(_call)
            embeddings.extend(response["embeddings"])
            logger.info("Embedded %d/%d text(s) with %s", len(embeddings), len(texts), self.model)
        return embeddings
