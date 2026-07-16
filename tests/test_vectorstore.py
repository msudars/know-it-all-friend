from pathlib import Path

from know_it_all_friend.retrieval.search import search_index
from know_it_all_friend.vectorstore.local_store import LocalVectorStore, build_index
from tests.conftest import BagOfWordsEmbedder, make_chunk


def test_build_index_and_query_ranks_by_similarity() -> None:
    chunks = [
        make_chunk("c1", "alpha alpha alpha"),
        make_chunk("c2", "beta beta beta"),
        make_chunk("c3", "alpha beta"),
    ]
    store = build_index(chunks, BagOfWordsEmbedder())

    results = store.query([1.0, 0.0, 0.0, 0.0], top_k=2)

    assert len(store) == 3
    assert [chunk.chunk_id for chunk, _ in results] == ["c1", "c3"]
    assert results[0][1] > results[1][1]


def test_query_on_empty_index_returns_nothing() -> None:
    store = build_index([], BagOfWordsEmbedder())

    assert len(store) == 0
    assert store.query([1.0, 0.0, 0.0, 0.0]) == []


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    chunks = [make_chunk("c1", "alpha"), make_chunk("c2", "beta")]
    store = build_index(chunks, BagOfWordsEmbedder())
    index_dir = tmp_path / "index"

    store.save(index_dir)
    loaded = LocalVectorStore.load(index_dir)

    assert len(loaded) == 2
    assert loaded.embedding_model == "bag-of-words-test"
    assert (index_dir / "embeddings.npy").exists()
    assert (index_dir / "chunks.json").exists()
    assert (index_dir / "config.json").exists()
    top_chunk, _ = loaded.query([0.0, 1.0, 0.0, 0.0], top_k=1)[0]
    assert top_chunk.chunk_id == "c2"


def test_search_index_returns_traceable_results() -> None:
    chunks = [make_chunk("c1", "alpha alpha"), make_chunk("c2", "gamma gamma")]
    store = build_index(chunks, BagOfWordsEmbedder())

    results = search_index("gamma", store, BagOfWordsEmbedder(), top_k=1)

    assert results[0].chunk_id == "c2"
    assert results[0].document_id == "document_001"
    assert results[0].title == "Example Report"
    assert results[0].source_file == "input/report.txt"
    assert results[0].heading == "Section"
    assert results[0].score > 0
