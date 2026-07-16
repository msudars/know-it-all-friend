"""Local on-disk vector store (Phase 7).

The index is three plain, inspectable files in one directory:

- ``embeddings.npy`` -- one row per chunk
- ``chunks.json``    -- the chunk records, row-aligned with the embeddings
- ``config.json``    -- which embedding model built the index
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from typing import cast
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from know_it_all_friend.chunking.chunker import Chunk
from know_it_all_friend.embeddings.base import BaseEmbedder

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class LocalVectorStore:
    def __init__(self, embeddings: np.ndarray, chunks: list[Chunk], embedding_model: str):
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(
                f"Row mismatch: {embeddings.shape[0]} embeddings for {len(chunks)} chunks"
            )
        self._embeddings = embeddings.astype(np.float32)
        self._chunks = chunks
        self.embedding_model = embedding_model
        self._chunk_id_to_idx = {chunk.chunk_id: i for i, chunk in enumerate(chunks)}
        self._bm25: BM25Okapi | None = None

    def __len__(self) -> int:
        return len(self._chunks)

    def query(self, vector: list[float], top_k: int = 5) -> list[tuple[Chunk, float]]:
        """Return the ``top_k`` chunks most similar to ``vector`` (cosine)."""
        if not self._chunks:
            return []
        query_vec = np.asarray(vector, dtype=np.float32)
        norms = np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(query_vec)
        # Zero-norm rows (e.g. empty text embedded to zeros) score 0 instead
        # of dividing by zero.
        with np.errstate(divide="ignore", invalid="ignore"):
            scores = np.where(norms > 0, self._embeddings @ query_vec / norms, 0.0)
        order = np.argsort(scores)[::-1][:top_k]
        return [(self._chunks[i], float(scores[i])) for i in order]

    def _ensure_bm25(self) -> BM25Okapi | None:
        if self._bm25 is None and self._chunks:
            self._bm25 = BM25Okapi([_tokenize(chunk.text) for chunk in self._chunks])
        return self._bm25

    def keyword_search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        """Return the ``top_k`` best BM25 keyword matches as ``(chunk, score)`` pairs.

        Complements vector search for exact-term queries (names, IDs,
        numbers) that embeddings can miss. The BM25 index is built lazily
        over all chunk text and cached for the lifetime of this store.
        """
        bm25 = self._ensure_bm25()
        if bm25 is None:
            return []
        scores = bm25.get_scores(_tokenize(query))
        order = np.argsort(scores)[::-1][:top_k]
        return [(self._chunks[i], float(scores[i])) for i in order]

    def mmr_select(
        self,
        query_vector: list[float],
        candidate_chunk_ids: list[str],
        top_k: int,
        lambda_mult: float = 0.5,
    ) -> list[str]:
        """Re-order ``candidate_chunk_ids`` by Maximal Marginal Relevance.

        Iteratively picks the candidate that maximizes relevance to the
        query minus similarity to what's already been selected, so
        near-duplicate chunks don't crowd out distinct ones. Returns up to
        ``top_k`` chunk IDs in selection order.
        """
        if not candidate_chunk_ids:
            return []
        idx = [self._chunk_id_to_idx[cid] for cid in candidate_chunk_ids]
        candidates = _normalize(self._embeddings[idx])
        query = _normalize(np.asarray([query_vector], dtype=np.float32))[0]
        relevance = candidates @ query

        selected: list[int] = []
        remaining = list(range(len(idx)))
        while remaining and len(selected) < top_k:
            if not selected:
                best = max(remaining, key=lambda i: relevance[i])
            else:
                selected_vecs = candidates[selected]
                sims = candidates[remaining] @ selected_vecs.T
                max_sim = sims.max(axis=1)
                mmr_scores = lambda_mult * relevance[remaining] - (1 - lambda_mult) * max_sim
                best = remaining[int(np.argmax(mmr_scores))]
            selected.append(best)
            remaining.remove(best)
        return [candidate_chunk_ids[i] for i in selected]

    def save(self, index_dir: Path) -> None:
        index_dir = Path(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "embeddings.npy", self._embeddings)
        with (index_dir / "chunks.json").open("w", encoding="utf-8") as f:
            json.dump([asdict(c) for c in self._chunks], f, indent=2)
        with (index_dir / "config.json").open("w", encoding="utf-8") as f:
            json.dump({"embedding_model": self.embedding_model}, f, indent=2)
        logger.info("Saved index with %d chunk(s) to %s", len(self), index_dir)

    @classmethod
    def load(cls, index_dir: Path) -> LocalVectorStore:
        index_dir = Path(index_dir)
        embeddings = np.load(index_dir / "embeddings.npy")
        chunk_data = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
        config = json.loads((index_dir / "config.json").read_text(encoding="utf-8"))
        return cls(
            embeddings=embeddings,
            chunks=[Chunk(**entry) for entry in chunk_data],
            embedding_model=config["embedding_model"],
        )


def build_index(chunks: list[Chunk], embedder: BaseEmbedder) -> LocalVectorStore:
    """Embed every chunk and return an in-memory index ready to save."""
    vectors = embedder.embed_texts([chunk.text for chunk in chunks])
    embeddings = (
        np.asarray(vectors, dtype=np.float32) if vectors else np.empty((0, 0), dtype=np.float32)
    )
    logger.info("Built index over %d chunk(s) with %s", len(chunks), embedder.model)
    return LocalVectorStore(embeddings=embeddings, chunks=chunks, embedding_model=embedder.model)


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms
