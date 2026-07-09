"""Semantic search over the vector index (Phase 8)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.vectorstore.local_store import LocalVectorStore

logger = logging.getLogger(__name__)

_RRF_K = 60


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
    mode: Literal["vector", "hybrid"] = "vector",
    alpha: float = 0.5,
    score_threshold: float | None = None,
    diversify: bool = False,
    fetch_k: int = 20,
    filter_document_ids: set[str] | None = None,
) -> list[SearchResult]:
    """Embed ``query`` and return the ``top_k`` most relevant chunks.

    The index records which embedding model produced it; querying with a
    different model would compare vectors from incompatible spaces, so that
    is rejected up front rather than returning silently meaningless scores.

    ``mode="hybrid"`` fuses vector similarity with BM25 keyword search via
    Reciprocal Rank Fusion (weighted by ``alpha`` toward the vector side),
    which catches exact-term queries (names, IDs, numbers) that embeddings
    alone can miss. ``diversify=True`` re-selects the final ``top_k`` from a
    ``fetch_k``-sized candidate pool using Maximal Marginal Relevance, so
    near-duplicate chunks don't crowd out distinct ones. ``score_threshold``
    drops low-confidence results instead of always returning ``top_k``
    regardless of relevance. ``filter_document_ids`` restricts results to a
    specific set of documents.

    All of these are opt-in with defaults that reproduce plain top-k vector
    search, unchanged from before these options existed.
    """
    if embedder.model != store.embedding_model:
        raise ValueError(
            f"Index was built with embedding model {store.embedding_model!r} "
            f"but the query embedder is {embedder.model!r}; re-run `kiaf index` "
            "or pass the matching --embed-model."
        )

    query_vector = embedder.embed_query(query)

    pool = top_k
    if mode == "hybrid" or diversify:
        pool = max(pool, fetch_k)
    if filter_document_ids is not None:
        pool = max(pool, top_k * 5)
    if len(store):
        pool = min(pool, len(store))

    vector_hits = store.query(query_vector, top_k=pool)
    chunk_by_id = {chunk.chunk_id: chunk for chunk, _ in vector_hits}

    if mode == "hybrid":
        keyword_hits = store.keyword_search(query, top_k=pool)
        for chunk, _ in keyword_hits:
            chunk_by_id.setdefault(chunk.chunk_id, chunk)

        fused: dict[str, float] = {}
        for rank, (chunk, _) in enumerate(vector_hits, start=1):
            fused[chunk.chunk_id] = fused.get(chunk.chunk_id, 0.0) + alpha / (_RRF_K + rank)
        for rank, (chunk, _) in enumerate(keyword_hits, start=1):
            fused[chunk.chunk_id] = fused.get(chunk.chunk_id, 0.0) + (1 - alpha) / (_RRF_K + rank)
        scored = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    else:
        scored = [(chunk.chunk_id, score) for chunk, score in vector_hits]

    if filter_document_ids is not None:
        scored = [(cid, s) for cid, s in scored if chunk_by_id[cid].document_id in filter_document_ids]

    if diversify and scored:
        candidate_ids = [cid for cid, _ in scored[:fetch_k]]
        score_by_id = dict(scored)
        selected_ids = store.mmr_select(query_vector, candidate_ids, top_k)
        scored = [(cid, score_by_id[cid]) for cid in selected_ids]
    else:
        scored = scored[:top_k]

    if score_threshold is not None:
        scored = [(cid, s) for cid, s in scored if s >= score_threshold]

    results = [
        SearchResult(
            chunk_id=chunk_by_id[cid].chunk_id,
            document_id=chunk_by_id[cid].document_id,
            title=chunk_by_id[cid].title,
            source_file=chunk_by_id[cid].source_file,
            heading=chunk_by_id[cid].heading,
            text=chunk_by_id[cid].text,
            score=score,
        )
        for cid, score in scored
    ]
    logger.info("Query %r (mode=%s) returned %d result(s)", query, mode, len(results))
    return results
