"""Chunking engine: split Markdown documents into retrievable units (Phase 5)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from know_it_all_friend.metadata.extractor import DocumentMetadata

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 1500

_ATX_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
_CODE_FENCE = re.compile(r"^(```|~~~)")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    title: str
    source_file: str
    heading: str | None
    text: str


def _split_sections(markdown_text: str) -> list[tuple[str | None, str]]:
    """Split Markdown into ``(heading, text)`` sections at ATX headings.

    The heading line stays part of its section's text so chunks keep that
    context for embedding; the extracted heading is also carried separately
    on each chunk. Lines inside fenced code blocks are never treated as
    headings. Content before the first heading forms a section with
    ``heading=None``.
    """
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    in_fence = False

    for line in markdown_text.splitlines():
        if _CODE_FENCE.match(line):
            in_fence = not in_fence
        heading_match = None if in_fence else _ATX_HEADING.match(line)
        if heading_match:
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = heading_match.group(1)
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines))

    return [
        (heading, text)
        for heading, lines in sections
        if (text := "\n".join(lines).strip())
    ]


def _split_oversized(text: str, max_chars: int) -> list[str]:
    """Hard-split ``text`` into pieces of at most ``max_chars``, breaking at
    the last whitespace before the limit when there is one."""
    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        cut = window.rstrip().rfind(" ")
        if cut <= 0:
            cut = max_chars
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _pack_paragraphs(section_text: str, max_chars: int) -> list[str]:
    """Pack a section's paragraphs into pieces of at most ``max_chars``."""
    if len(section_text) <= max_chars:
        return [section_text]

    pieces: list[str] = []
    buffer = ""
    for paragraph in re.split(r"\n{2,}", section_text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        if buffer:
            pieces.append(buffer)
            buffer = ""
        if len(paragraph) <= max_chars:
            buffer = paragraph
        else:
            pieces.extend(_split_oversized(paragraph, max_chars))
    if buffer:
        pieces.append(buffer)
    return pieces


def chunk_markdown(
    markdown_text: str,
    doc: DocumentMetadata,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[Chunk]:
    """Chunk one document's Markdown into units of at most ``max_chars``.

    Chunk IDs are ``<document_id>_chunk_<n>`` with ``n`` assigned in
    document order, so re-running the pipeline on unchanged input yields
    the same IDs.
    """
    chunks: list[Chunk] = []
    for heading, section_text in _split_sections(markdown_text):
        for piece in _pack_paragraphs(section_text, max_chars):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.document_id}_chunk_{len(chunks):04d}",
                    document_id=doc.document_id,
                    title=doc.title,
                    source_file=doc.source_file,
                    heading=heading,
                    text=piece,
                )
            )
    return chunks


def chunk_documents(
    docs: list[DocumentMetadata],
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[Chunk]:
    """Chunk every document in the metadata index.

    A document whose Markdown file cannot be read is logged and skipped;
    the rest of the collection still gets chunked.
    """
    chunks: list[Chunk] = []
    for doc in docs:
        try:
            markdown_text = Path(doc.markdown_file).read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Skipping %s: could not read %s: %s", doc.document_id, doc.markdown_file, exc)
            continue
        doc_chunks = chunk_markdown(markdown_text, doc, max_chars=max_chars)
        chunks.extend(doc_chunks)
        logger.info("Chunked %s into %d chunk(s)", doc.document_id, len(doc_chunks))
    return chunks


def write_chunks(chunks: list[Chunk], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in chunks], f, indent=2)
    logger.info("Wrote %d chunk(s) to %s", len(chunks), output_path)


def load_chunks(chunks_path: Path) -> list[Chunk]:
    chunks_path = Path(chunks_path)
    data = json.loads(chunks_path.read_text(encoding="utf-8"))
    return [Chunk(**entry) for entry in data]
