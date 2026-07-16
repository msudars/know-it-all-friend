import json
from pathlib import Path

from know_it_all_friend.enrichment.extractor import (
    ENTITY_TYPES,
    DocumentEntities,
    enrich_documents,
    extract_entities,
    load_entities,
    write_entities,
)
from know_it_all_friend.metadata.extractor import DocumentMetadata
from tests.conftest import CannedLLM, FailingLLM


def _doc(tmp_path: Path, markdown: str, doc_id: str = "document_001") -> DocumentMetadata:
    markdown_path = tmp_path / f"{doc_id}.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    return DocumentMetadata(
        document_id=doc_id,
        title="Example Report",
        source_file=f"input/{doc_id}.txt",
        markdown_file=markdown_path.as_posix(),
        extension="txt",
        size_bytes=123,
        word_count=len(markdown.split()),
    )


def test_extract_entities_parses_and_cleans_reply() -> None:
    reply = json.dumps(
        {
            "people": ["Jane  Doe", "Jane Doe", 42],
            "topics": ["Topic A"],
            "unknown_key": ["dropped"],
            "locations": "not a list",
        }
    )
    llm = CannedLLM(reply)

    entities = extract_entities("Document text about Topic A.", llm)

    assert entities["people"] == ["Jane Doe"]
    assert entities["topics"] == ["Topic A"]
    assert entities["locations"] == []
    assert "unknown_key" not in entities
    assert set(entities) == set(ENTITY_TYPES)
    assert "Document text about Topic A." in llm.prompts[0]


def test_extract_entities_handles_fenced_json() -> None:
    llm = CannedLLM('Here you go:\n```json\n{"topics": ["Topic A"]}\n```')

    entities = extract_entities("text", llm)

    assert entities["topics"] == ["Topic A"]


def test_extract_entities_survives_garbage_reply() -> None:
    llm = CannedLLM("I cannot help with that.")

    entities = extract_entities("text", llm)

    assert entities == {entity_type: [] for entity_type in ENTITY_TYPES}


def test_extract_entities_truncates_long_documents() -> None:
    llm = CannedLLM("{}")

    extract_entities("x" * 20_000, llm, max_chars=100)

    assert len(llm.prompts[0]) < 1_000


def test_enrich_documents_skips_failures_and_continues(tmp_path: Path) -> None:
    good = _doc(tmp_path, "# Good\n\nProject Alpha uses Technology A.\n", doc_id="document_001")
    missing = DocumentMetadata(
        document_id="document_002",
        title="Missing",
        source_file="input/missing.txt",
        markdown_file=(tmp_path / "missing.md").as_posix(),
        extension="txt",
        size_bytes=0,
        word_count=0,
    )
    llm = CannedLLM('{"projects": ["Project Alpha"], "technologies": ["Technology A"]}')

    enriched = enrich_documents([good, missing], llm)

    assert [e.document_id for e in enriched] == ["document_001"]
    assert enriched[0].entities["projects"] == ["Project Alpha"]


def test_enrich_documents_skips_model_failures(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "# Doc\n\ntext\n")

    assert enrich_documents([doc], FailingLLM()) == []


def test_write_and_load_entities_round_trip(tmp_path: Path) -> None:
    enriched = [
        DocumentEntities(document_id="document_001", entities={"topics": ["Topic A"]}),
    ]
    path = tmp_path / "entities.json"

    write_entities(enriched, path)

    assert load_entities(path) == enriched
