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
DEFAULT_OVERLAP_CHARS = 200

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


def _rfind_whitespace(text: str, limit: int) -> int:
    """Return the index of the last whitespace char within ``text[:limit]``, or -1."""
    return max(text.rfind(" ", 0, limit), text.rfind("\n", 0, limit), text.rfind("\t", 0, limit))


def _split_oversized(text: str, max_chars: int) -> list[str]:
    """Hard-split ``text`` into pieces of at most ``max_chars``, breaking at
    the last whitespace before the limit when there is one."""
    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        cut = _rfind_whitespace(remaining, max_chars)
        if cut <= 0:
            cut = max_chars
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _lstrip_partial_word(text: str) -> str:
    """Drop a leading word fragment so ``text`` starts at a whole word.

    Used on a trailing slice of a longer string (overlap context), where the
    first characters may be the tail end of a word that started earlier in
    the original string. A slice with no whitespace at all (e.g. a long URL)
    is returned unchanged since there's no word boundary to trim to.
    """
    for i, ch in enumerate(text):
        if ch.isspace():
            return text[i:].strip()
    return text


def _overlap_tail(previous: str, budget: int) -> str:
    """Return up to ``budget`` trailing chars of ``previous``, trimmed to a word boundary."""
    if budget <= 0:
        return ""
    return _lstrip_partial_word(previous[-budget:])


def _pack_paragraphs(section_text: str, max_chars: int, overlap_chars: int = 0) -> list[str]:
    """Pack a section's paragraphs into pieces of at most ``max_chars``.

    A paragraph longer than ``max_chars`` is hard-split so no piece can
    exceed the limit regardless of input formatting. When ``overlap_chars``
    is set, each piece after the first is seeded with a word-boundary-safe
    tail of the previous piece (capped so the total still respects
    ``max_chars``), so retrieval doesn't lose context that straddles a
    chunk boundary.
    """
    if len(section_text) <= max_chars:
        return [section_text]

    paragraphs: list[str] = []
    for paragraph in re.split(r"\n{2,}", section_text):
        paragraph = paragraph.strip()
        if paragraph:
            if len(paragraph) <= max_chars:
                paragraphs.append(paragraph)
            else:
                paragraphs.extend(_split_oversized(paragraph, max_chars))

    pieces: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        pieces.append(buffer)
        budget = min(overlap_chars, max_chars - len(paragraph) - 2)
        tail = _overlap_tail(buffer, budget)
        buffer = f"{tail}\n\n{paragraph}" if tail else paragraph
    if buffer:
        pieces.append(buffer)
    return pieces


def chunk_markdown(
    markdown_text: str,
    doc: DocumentMetadata,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    """Chunk one document's Markdown into units of at most ``max_chars``.

    Chunk IDs are ``<document_id>_chunk_<n>`` with ``n`` assigned in
    document order, so re-running the pipeline on unchanged input yields
    the same IDs. When ``overlap_chars`` is set, consecutive pieces within
    the same section share trailing/leading context so retrieval doesn't
    lose information that straddles a chunk boundary; overlap never crosses
    a heading boundary since sections are packed independently.
    """
    chunks: list[Chunk] = []
    for heading, section_text in _split_sections(markdown_text):
        for piece in _pack_paragraphs(section_text, max_chars, overlap_chars=overlap_chars):
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
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
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
        doc_chunks = chunk_markdown(markdown_text, doc, max_chars=max_chars, overlap_chars=overlap_chars)
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
