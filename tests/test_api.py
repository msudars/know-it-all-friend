from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from know_it_all_friend.api.app import create_app
from know_it_all_friend.metadata.extractor import DocumentMetadata, write_metadata
from know_it_all_friend.vectorstore.local_store import build_index
from tests.conftest import BagOfWordsEmbedder, CannedLLM, make_chunk


def _client(tmp_path: Path) -> TestClient:
    metadata_path = tmp_path / "documents.json"
    write_metadata(
        [
            DocumentMetadata(
                document_id="document_001",
                title="Example Report",
                source_file="input/report.txt",
                markdown_file="storage/markdown/document_001.md",
                extension="txt",
                size_bytes=123,
                word_count=10,
            )
        ],
        metadata_path,
    )
    store = build_index([make_chunk("c1", "alpha facts"), make_chunk("c2", "beta facts")], BagOfWordsEmbedder())
    app = create_app(
        metadata_path=metadata_path,
        store=store,
        embedder=BagOfWordsEmbedder(),
        llm=CannedLLM(),
    )
    return TestClient(app)


def test_health(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/health").json() == {"status": "ok"}


def test_documents_returns_metadata(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/documents")

    assert response.status_code == 200
    assert response.json()[0]["document_id"] == "document_001"
    assert response.json()[0]["title"] == "Example Report"


def test_documents_without_metadata_returns_503(tmp_path: Path) -> None:
    app = create_app(metadata_path=tmp_path / "missing.json")

    response = TestClient(app).get("/documents")

    assert response.status_code == 503


def test_search_returns_ranked_results(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/search", params={"q": "beta", "top_k": 1})

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["chunk_id"] == "c2"
    assert results[0]["source_file"] == "input/report.txt"
    assert results[0]["score"] > 0


def test_search_without_index_returns_503(tmp_path: Path) -> None:
    app = create_app(index_dir=tmp_path / "no-index")

    response = TestClient(app).get("/search", params={"q": "anything"})

    assert response.status_code == 503


def test_ask_returns_answer_with_sources(tmp_path: Path) -> None:
    response = _client(tmp_path).post("/ask", json={"question": "alpha", "top_k": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Canned answer [1]."
    assert body["sources"][0]["chunk_id"] == "c1"
