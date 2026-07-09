import json
from pathlib import Path

from know_it_all_friend.chunking.chunker import (
    chunk_documents,
    chunk_markdown,
    load_chunks,
    write_chunks,
)
from know_it_all_friend.metadata.extractor import DocumentMetadata


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


def test_chunk_markdown_splits_at_headings(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "preamble\n\n# Intro\n\nintro text\n\n## Methods\n\nmethods text\n")

    chunks = chunk_markdown(Path(doc.markdown_file).read_text(encoding="utf-8"), doc)

    assert [c.heading for c in chunks] == [None, "Intro", "Methods"]
    assert chunks[1].text == "# Intro\n\nintro text"
    assert chunks[0].text == "preamble"


def test_chunk_ids_are_stable_and_sequential(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "# A\n\ntext\n\n# B\n\ntext\n")
    markdown = Path(doc.markdown_file).read_text(encoding="utf-8")

    first = chunk_markdown(markdown, doc)
    second = chunk_markdown(markdown, doc)

    assert [c.chunk_id for c in first] == ["document_001_chunk_0000", "document_001_chunk_0001"]
    assert first == second


def test_chunks_preserve_document_metadata(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "# A\n\ntext\n")

    chunks = chunk_documents([doc])

    assert chunks[0].document_id == "document_001"
    assert chunks[0].title == "Example Report"
    assert chunks[0].source_file == "input/document_001.txt"


def test_long_sections_are_packed_within_max_chars(tmp_path: Path) -> None:
    paragraphs = "\n\n".join(f"paragraph {i} " + "x" * 40 for i in range(10))
    doc = _doc(tmp_path, f"# Long\n\n{paragraphs}\n")

    chunks = chunk_markdown(Path(doc.markdown_file).read_text(encoding="utf-8"), doc, max_chars=120)

    assert len(chunks) > 1
    assert all(len(c.text) <= 120 for c in chunks)
    assert all(c.heading == "Long" for c in chunks)


def test_oversized_paragraph_is_hard_split(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "word " * 100)

    chunks = chunk_markdown(
        Path(doc.markdown_file).read_text(encoding="utf-8"), doc, max_chars=80, overlap_chars=0
    )

    assert len(chunks) > 1
    assert all(len(c.text) <= 80 for c in chunks)
    assert " ".join(c.text for c in chunks).split() == ["word"] * 100


def test_overlap_carries_word_boundary_safe_tail_into_next_chunk(tmp_path: Path) -> None:
    paragraphs = "\n\n".join(f"paragraph {i} with some distinct words here" for i in range(10))
    doc = _doc(tmp_path, f"# Section\n\n{paragraphs}\n")

    chunks = chunk_markdown(
        Path(doc.markdown_file).read_text(encoding="utf-8"), doc, max_chars=150, overlap_chars=50
    )

    assert len(chunks) > 1
    for previous, current in zip(chunks, chunks[1:]):
        tail_words = previous.text.split()[-3:]
        assert any(word in current.text.split("\n\n")[0] for word in tail_words)


def test_overlap_does_not_cross_heading_boundary(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "# Section One\nalpha content here\n\n# Section Two\nbeta content here\n")

    chunks = chunk_markdown(
        Path(doc.markdown_file).read_text(encoding="utf-8"), doc, max_chars=1500, overlap_chars=200
    )

    assert [c.text for c in chunks] == [
        "# Section One\nalpha content here",
        "# Section Two\nbeta content here",
    ]


def test_overlap_respects_max_chars_budget(tmp_path: Path) -> None:
    paragraphs = "\n\n".join(f"paragraph number {i} with some words" for i in range(20))
    doc = _doc(tmp_path, f"# Big Section\n\n{paragraphs}\n")

    chunks = chunk_markdown(
        Path(doc.markdown_file).read_text(encoding="utf-8"), doc, max_chars=100, overlap_chars=200
    )

    assert len(chunks) > 1
    assert all(len(c.text) <= 100 for c in chunks)


def test_headings_inside_code_fences_are_ignored(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "# Real\n\n```\n# not a heading\n```\n\nmore text\n")

    chunks = chunk_markdown(Path(doc.markdown_file).read_text(encoding="utf-8"), doc)

    assert len(chunks) == 1
    assert chunks[0].heading == "Real"


def test_chunk_documents_skips_unreadable_markdown(tmp_path: Path) -> None:
    good = _doc(tmp_path, "# Good\n\ntext\n", doc_id="document_001")
    bad = DocumentMetadata(
        document_id="document_002",
        title="Missing",
        source_file="input/missing.txt",
        markdown_file=(tmp_path / "missing.md").as_posix(),
        extension="txt",
        size_bytes=0,
        word_count=0,
    )

    chunks = chunk_documents([good, bad])

    assert {c.document_id for c in chunks} == {"document_001"}


def test_write_and_load_chunks_round_trip(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "# A\n\ntext\n")
    chunks = chunk_documents([doc])
    chunks_path = tmp_path / "chunks.json"

    write_chunks(chunks, chunks_path)
    loaded = load_chunks(chunks_path)

    assert loaded == chunks
    data = json.loads(chunks_path.read_text(encoding="utf-8"))
    assert data[0]["chunk_id"] == "document_001_chunk_0000"
