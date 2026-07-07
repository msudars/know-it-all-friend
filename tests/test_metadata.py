import json
from pathlib import Path

from know_it_all_friend.conversion.pipeline import ConversionResult
from know_it_all_friend.ingestion.inventory import DocumentRecord
from know_it_all_friend.metadata.extractor import (
    build_metadata,
    extract_title,
    write_metadata_index,
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


def _success(tmp_path: Path, doc_id: str, markdown: str) -> ConversionResult:
    markdown_path = tmp_path / f"{doc_id}.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    return ConversionResult(
        document_id=doc_id,
        source_path="irrelevant",
        markdown_path=markdown_path.as_posix(),
        status="success",
        error=None,
        timestamp="2026-01-01T00:00:00+00:00",
    )


def test_extract_title_returns_first_h1() -> None:
    assert extract_title("intro\n# Example Report\n\n# Second\n") == "Example Report"


def test_extract_title_returns_none_without_h1() -> None:
    assert extract_title("## Only a subsection\nbody text\n") is None


def test_build_metadata_uses_markdown_heading_as_title(tmp_path: Path) -> None:
    record = _record(tmp_path, "report.txt")
    result = _success(tmp_path, "document_001", "# Example Report\n\nBody.\n")

    entries = build_metadata([record], [result])

    assert entries[0].title == "Example Report"
    assert entries[0].markdown_file == result.markdown_path
    assert entries[0].source_file == record.path
    assert entries[0].date is not None


def test_build_metadata_falls_back_to_filename_stem(tmp_path: Path) -> None:
    record = _record(tmp_path, "quarterly_notes.txt")
    result = _success(tmp_path, "document_001", "no heading here\n")

    entries = build_metadata([record], [result])

    assert entries[0].title == "quarterly_notes"


def test_build_metadata_covers_failed_conversions(tmp_path: Path) -> None:
    record = _record(tmp_path, "broken.pdf")
    failed = ConversionResult(
        document_id="document_001",
        source_path=record.path,
        markdown_path=None,
        status="failed",
        error="simulated conversion failure",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    entries = build_metadata([record], [failed])

    assert entries[0].markdown_file is None
    assert entries[0].title == "broken"


def test_build_metadata_survives_missing_markdown_file(tmp_path: Path) -> None:
    record = _record(tmp_path, "gone.txt")
    result = ConversionResult(
        document_id="document_001",
        source_path=record.path,
        markdown_path=(tmp_path / "missing.md").as_posix(),
        status="success",
        error=None,
        timestamp="2026-01-01T00:00:00+00:00",
    )

    entries = build_metadata([record], [result])

    assert entries[0].title == "gone"


def test_write_metadata_index_round_trip(tmp_path: Path) -> None:
    record = _record(tmp_path, "report.txt")
    result = _success(tmp_path, "document_001", "# Example Report\n")
    entries = build_metadata([record], [result])
    index_path = tmp_path / "metadata.json"

    write_metadata_index(entries, index_path)

    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert data[0]["document_id"] == "document_001"
    assert data[0]["title"] == "Example Report"
    assert data[0]["author"] is None
