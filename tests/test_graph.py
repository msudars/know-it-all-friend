from pathlib import Path

from know_it_all_friend.enrichment.extractor import DocumentEntities
from know_it_all_friend.graph.builder import (
    build_graph,
    entities_of_document,
    load_graph,
    related_to_entity,
    write_graph,
)
from know_it_all_friend.metadata.extractor import DocumentMetadata


def _doc(doc_id: str, title: str) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=doc_id,
        title=title,
        source_file=f"input/{doc_id}.txt",
        markdown_file=f"storage/markdown/{doc_id}.md",
        extension="txt",
        size_bytes=123,
        word_count=100,
    )


def _graph() -> dict:
    docs = [_doc("document_001", "Report A"), _doc("document_002", "Report B")]
    enriched = [
        DocumentEntities(
            document_id="document_001",
            entities={
                "projects": ["Project Alpha"],
                "technologies": ["Technology A"],
                "topics": ["Topic A"],
            },
        ),
        DocumentEntities(
            document_id="document_002",
            entities={"projects": ["Project Alpha"], "technologies": ["Technology A"]},
        ),
    ]
    return build_graph(docs, enriched)


def test_build_graph_collects_entities_and_documents() -> None:
    graph = _graph()

    assert graph["entities"]["Project Alpha"] == {
        "type": "projects",
        "documents": ["document_001", "document_002"],
    }
    assert graph["documents"]["document_001"]["title"] == "Report A"


def test_build_graph_weights_co_occurrences_by_shared_documents() -> None:
    graph = _graph()

    edges = {(e["source"], e["target"]): e["weight"] for e in graph["co_occurrences"]}
    assert edges[("Project Alpha", "Technology A")] == 2
    assert edges[("Project Alpha", "Topic A")] == 1
    assert graph["co_occurrences"][0]["weight"] == 2  # sorted by weight, heaviest first


def test_related_to_entity_is_case_insensitive() -> None:
    graph = _graph()

    related = related_to_entity(graph, "project alpha")

    assert related is not None
    assert related["name"] == "Project Alpha"
    assert related["type"] == "projects"
    assert [d["document_id"] for d in related["documents"]] == ["document_001", "document_002"]
    assert related["related_entities"][0] == {"name": "Technology A", "weight": 2}


def test_related_to_unknown_entity_returns_none() -> None:
    assert related_to_entity(_graph(), "Unknown Thing") is None


def test_entities_of_document_groups_by_type() -> None:
    grouped = entities_of_document(_graph(), "document_001")

    assert grouped == {
        "projects": ["Project Alpha"],
        "technologies": ["Technology A"],
        "topics": ["Topic A"],
    }


def test_entities_of_unknown_document_returns_none() -> None:
    assert entities_of_document(_graph(), "document_999") is None


def test_write_and_load_graph_round_trip(tmp_path: Path) -> None:
    graph = _graph()
    path = tmp_path / "graph.json"

    write_graph(graph, path)

    assert load_graph(path) == graph
