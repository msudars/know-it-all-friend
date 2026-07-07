"""Semantic search over the vector index (Phase 8)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.vectorstore.local_store import LocalVectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    document_id: str
    title: str
    source_file: str
    heading: str | None
    text: str
    score: float


def search_index(
    query: str,
    store: LocalVectorStore,
    embedder: BaseEmbedder,
    top_k: int = 5,
) -> list[SearchResult]:
    """Embed ``query`` and return the ``top_k`` most similar chunks.

    Every result carries its chunk and document identifiers so hits are
    traceable back to the source file.
    """
    query_vector = embedder.embed_query(query)
    results = [
        SearchResult(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            title=chunk.title,
            source_file=chunk.source_file,
            heading=chunk.heading,
            text=chunk.text,
            score=score,
        )
        for chunk, score in store.query(query_vector, top_k=top_k)
    ]
    logger.info("Query %r returned %d result(s)", query, len(results))
    return results
