import json
from pathlib import Path

from know_it_all_friend.ingestion.inventory import DocumentRecord
from know_it_all_friend.metadata.extractor import (
    build_document_metadata,
    extract_title,
    load_metadata,
    write_metadata,
)


def _record(tmp_path: Path, name: str, doc_id: str = "document_001") -> DocumentRecord:
    file_path = tmp_path / name
    file_path.write_text("source content", encoding="utf-8")
    return DocumentRecord(
        id=doc_id,
        filename=name,
        extension=Path(name).suffix.lstrip("."),
        path=file_path.as_posix(),
        size_bytes=file_path.stat().st_size,
    )


def _success_entry(tmp_path: Path, doc_id: str, markdown: str) -> dict:
    markdown_path = tmp_path / f"{doc_id}.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    return {
        "document_id": doc_id,
        "source_path": "irrelevant",
        "markdown_path": markdown_path.as_posix(),
        "status": "success",
        "error": None,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }


def test_extract_title_returns_first_heading() -> None:
    assert extract_title("intro\n## Example Report\n\n# Later\n") == "Example Report"


def test_extract_title_returns_none_without_heading() -> None:
    assert extract_title("just body text\nno headings\n") is None


def test_build_document_metadata_uses_heading_and_counts_words(tmp_path: Path) -> None:
    record = _record(tmp_path, "report.txt")
    entry = _success_entry(tmp_path, "document_001", "# Example Report\n\nOne two three.\n")

    docs = build_document_metadata([record], [entry])

    assert docs[0].title == "Example Report"
    assert docs[0].markdown_file == entry["markdown_path"]
    assert docs[0].source_file == record.path
    assert docs[0].word_count == 6


def test_build_document_metadata_falls_back_to_filename_stem(tmp_path: Path) -> None:
    record = _record(tmp_path, "quarterly_notes.txt")
    entry = _success_entry(tmp_path, "document_001", "no heading here\n")

    docs = build_document_metadata([record], [entry])

    assert docs[0].title == "quarterly_notes"


def test_build_document_metadata_skips_failed_conversions(tmp_path: Path) -> None:
    good = _record(tmp_path, "good.txt", doc_id="document_001")
    bad = _record(tmp_path, "bad.pdf", doc_id="document_002")
    entries = [
        _success_entry(tmp_path, "document_001", "# Good\n"),
        {
            "document_id": "document_002",
            "source_path": bad.path,
            "markdown_path": None,
            "status": "failed",
            "error": "simulated conversion failure",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
    ]

    docs = build_document_metadata([good, bad], entries)

    assert [d.document_id for d in docs] == ["document_001"]


def test_build_document_metadata_skips_missing_markdown_file(tmp_path: Path) -> None:
    record = _record(tmp_path, "gone.txt")
    entry = {
        "document_id": "document_001",
        "source_path": record.path,
        "markdown_path": (tmp_path / "missing.md").as_posix(),
        "status": "success",
        "error": None,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }

    docs = build_document_metadata([record], [entry])

    assert docs == []


def test_write_and_load_metadata_round_trip(tmp_path: Path) -> None:
    record = _record(tmp_path, "report.txt")
    entry = _success_entry(tmp_path, "document_001", "# Example Report\n")
    docs = build_document_metadata([record], [entry])
    index_path = tmp_path / "documents.json"

    write_metadata(docs, index_path)
    loaded = load_metadata(index_path)

    assert loaded == docs
    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert data[0]["title"] == "Example Report"


def test_extract_title_collapses_internal_whitespace() -> None:
    assert (
        extract_title("# Machine Learning Toolbox\x0b\x0bfor Batteries\n")
        == "Machine Learning Toolbox for Batteries"
    )
