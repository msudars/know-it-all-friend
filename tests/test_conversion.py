import json
from pathlib import Path

from know_it_all_friend.conversion.base import BaseConverter
from know_it_all_friend.conversion.pipeline import convert_documents, write_conversion_log
from know_it_all_friend.ingestion.inventory import DocumentRecord


class UppercaseConverter(BaseConverter):
    """Trivial stand-in converter so tests don't depend on markitdown or real files."""

    def convert(self, path: str | Path) -> str:
        return Path(path).read_text(encoding="utf-8").upper()


class SelectiveFailureConverter(BaseConverter):
    """Fails only for paths containing 'bad', to test partial-batch failure."""

    def convert(self, path: str | Path) -> str:
        if "bad" in Path(path).name:
            raise ValueError("simulated conversion failure")
        return Path(path).read_text(encoding="utf-8")


def _record(tmp_path: Path, name: str, content: str, doc_id: str = "document_001") -> DocumentRecord:
    file_path = tmp_path / name
    file_path.write_text(content, encoding="utf-8")
    return DocumentRecord(
        id=doc_id,
        filename=name,
        extension=Path(name).suffix.lstrip("."),
        path=file_path.as_posix(),
        size_bytes=file_path.stat().st_size,
    )


def test_convert_documents_writes_markdown_named_by_id(tmp_path: Path) -> None:
    record = _record(tmp_path, "a.txt", "hello")
    output_dir = tmp_path / "out"

    results = convert_documents([record], UppercaseConverter(), output_dir)

    assert results[0].status == "success"
    assert results[0].error is None
    assert (output_dir / "document_001.md").read_text(encoding="utf-8") == "HELLO"


def test_convert_documents_continues_after_one_failure(tmp_path: Path) -> None:
    good = _record(tmp_path, "good.txt", "hello", doc_id="document_001")
    bad = _record(tmp_path, "bad.txt", "irrelevant", doc_id="document_002")
    output_dir = tmp_path / "out"

    results = convert_documents([good, bad], SelectiveFailureConverter(), output_dir)

    assert results[0].status == "success"
    assert (output_dir / "document_001.md").exists()
    assert results[1].status == "failed"
    assert results[1].error == "simulated conversion failure"
    assert not (output_dir / "document_002.md").exists()


def test_write_conversion_log(tmp_path: Path) -> None:
    record = _record(tmp_path, "a.txt", "hello")
    results = convert_documents([record], UppercaseConverter(), tmp_path / "out")
    log_path = tmp_path / "log.json"

    write_conversion_log(results, log_path)

    data = json.loads(log_path.read_text(encoding="utf-8"))
    assert data[0]["status"] == "success"
    assert data[0]["document_id"] == "document_001"
