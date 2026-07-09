from pathlib import Path

import pytest

from know_it_all_friend.chunking.chunker import Chunk
from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.retrieval.search import search_index
from know_it_all_friend.vectorstore.local_store import LocalVectorStore, build_index

VOCAB = ["alpha", "beta", "gamma", "delta"]


class KeywordEmbedder(BaseEmbedder):
    """Deterministic stand-in embedder: counts occurrences of a fixed vocabulary.

    Texts sharing keywords get similar vectors, so retrieval behaves
    sensibly in tests without a real model or a running Ollama server.
    """

    model = "keyword-test-embedder"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(text.lower().count(word)) for word in VOCAB] for text in texts]


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=chunk_id.rsplit("_chunk_", 1)[0],
        title="Example",
        source_file="input/example.txt",
        heading="Section",
        text=text,
    )


def _store() -> LocalVectorStore:
    chunks = [
        _chunk("document_001_chunk_0000", "all about alpha and alpha again"),
        _chunk("document_001_chunk_0001", "this one covers beta"),
        _chunk("document_002_chunk_0000", "gamma and delta together"),
    ]
    return build_index(chunks, KeywordEmbedder())


def test_search_returns_most_similar_chunk_first() -> None:
    results = search_index("tell me about alpha", _store(), KeywordEmbedder(), top_k=2)

    assert len(results) == 2
    assert results[0].chunk_id == "document_001_chunk_0000"
    assert results[0].score > results[1].score


def test_search_rejects_mismatched_embedding_model() -> None:
    store = _store()
    other = KeywordEmbedder()
    other.model = "different-model"

    with pytest.raises(ValueError, match="different-model"):
        search_index("alpha", store, other)


def test_store_roundtrip_preserves_search_results(tmp_path: Path) -> None:
    store = _store()
    index_dir = tmp_path / "index"
    store.save(index_dir)

    loaded = LocalVectorStore.load(index_dir)

    assert len(loaded) == len(store)
    assert loaded.embedding_model == "keyword-test-embedder"
    original = search_index("beta", store, KeywordEmbedder(), top_k=1)
    reloaded = search_index("beta", loaded, KeywordEmbedder(), top_k=1)
    assert reloaded == original
    assert reloaded[0].chunk_id == "document_001_chunk_0001"


def test_search_empty_store_returns_no_results() -> None:
    store = build_index([], KeywordEmbedder())

    assert search_index("alpha", store, KeywordEmbedder()) == []


def test_hybrid_mode_finds_exact_term_vector_search_misses() -> None:
    """A rare term the toy KeywordEmbedder's fixed vocab can't represent (so
    vector search sees every chunk as an identical zero-vector) should still
    surface via BM25 keyword matching once hybrid mode weights it in.

    Three chunks (not two) so BM25's IDF for "zephyr" isn't the degenerate
    zero you get when a term sits in exactly half of a 2-document corpus.
    """
    chunks = [
        _chunk("document_001_chunk_0000", "the quarterly report mentions project zephyr by name"),
        _chunk("document_002_chunk_0000", "an unrelated memo about scheduling and logistics"),
        _chunk("document_003_chunk_0000", "notes from the weekly standup meeting"),
    ]
    store = build_index(chunks, KeywordEmbedder())

    # alpha=0.1 leans the RRF fusion toward the keyword signal, which is the
    # only signal that can distinguish these chunks here.
    results = search_index("zephyr", store, KeywordEmbedder(), top_k=1, mode="hybrid", alpha=0.1)

    assert len(results) == 1
    assert results[0].chunk_id == "document_001_chunk_0000"


def test_score_threshold_drops_low_relevance_results() -> None:
    results = search_index(
        "tell me about alpha", _store(), KeywordEmbedder(), top_k=3, score_threshold=0.5
    )

    assert len(results) == 1
    assert results[0].chunk_id == "document_001_chunk_0000"


def test_filter_document_ids_restricts_results_to_named_documents() -> None:
    results = search_index(
        "alpha beta gamma delta",
        _store(),
        KeywordEmbedder(),
        top_k=3,
        filter_document_ids={"document_002"},
    )

    assert len(results) == 1
    assert results[0].document_id == "document_002"


def test_diversify_prefers_distinct_chunks_over_near_duplicates() -> None:
    chunks = [
        _chunk("document_001_chunk_0000", "alpha alpha alpha beta"),
        _chunk("document_001_chunk_0001", "alpha alpha alpha beta"),  # near-duplicate of the above
        _chunk("document_002_chunk_0000", "alpha gamma gamma"),
    ]
    store = build_index(chunks, KeywordEmbedder())

    without_mmr = search_index("alpha", store, KeywordEmbedder(), top_k=2)
    with_mmr = search_index("alpha", store, KeywordEmbedder(), top_k=2, diversify=True, fetch_k=3)

    # Plain top-k picks both near-duplicates (highest raw relevance each).
    assert {r.chunk_id for r in without_mmr} == {
        "document_001_chunk_0000",
        "document_001_chunk_0001",
    }
    # MMR swaps the second near-duplicate for the distinct chunk instead.
    with_mmr_ids = {r.chunk_id for r in with_mmr}
    assert len(with_mmr) == 2
    assert "document_002_chunk_0000" in with_mmr_ids
    assert not {"document_001_chunk_0000", "document_001_chunk_0001"}.issubset(with_mmr_ids)
