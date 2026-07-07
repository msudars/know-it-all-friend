"""Metadata extraction: structured records for every converted document (Phase 3)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from know_it_all_friend.ingestion.inventory import DocumentRecord

logger = logging.getLogger(__name__)

_ATX_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    title: str
    source_file: str
    markdown_file: str
    extension: str
    size_bytes: int
    word_count: int


def extract_title(markdown_text: str) -> str | None:
    """Return the first ATX heading (any level) in ``markdown_text``, if any."""
    match = _ATX_HEADING.search(markdown_text)
    return match.group(1) if match else None


def build_document_metadata(
    records: list[DocumentRecord],
    conversion_log: list[dict],
) -> list[DocumentMetadata]:
    """Join the manifest with the conversion log and extract basic metadata.

    The document ID is the join key. Documents without a successful
    conversion are skipped (there is no Markdown to describe), and an
    unreadable Markdown file is logged and skipped rather than aborting the
    batch -- the pipeline-wide rule that one bad file must not block the
    rest.

    Only content-free basics are extracted here (title from the first
    heading, word count); authors, topics, and entities belong to the
    knowledge-enrichment phase.
    """
    markdown_by_id = {
        entry["document_id"]: entry["markdown_path"]
        for entry in conversion_log
        if entry.get("status") == "success" and entry.get("markdown_path")
    }

    docs: list[DocumentMetadata] = []
    for record in records:
        markdown_file = markdown_by_id.get(record.id)
        if markdown_file is None:
            logger.warning("Skipping %s: no successful conversion in the log", record.id)
            continue

        try:
            markdown_text = Path(markdown_file).read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Skipping %s: could not read %s: %s", record.id, markdown_file, exc)
            continue

        title = extract_title(markdown_text) or Path(record.filename).stem
        doc = DocumentMetadata(
            document_id=record.id,
            title=title,
            source_file=record.path,
            markdown_file=markdown_file,
            extension=record.extension,
            size_bytes=record.size_bytes,
            word_count=len(markdown_text.split()),
        )
        docs.append(doc)
        logger.info("Extracted metadata for %s: %r (%d words)", record.id, doc.title, doc.word_count)

    return docs


def write_metadata(docs: list[DocumentMetadata], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(d) for d in docs], f, indent=2)
    logger.info("Wrote metadata index with %d entries to %s", len(docs), output_path)


def load_metadata(metadata_path: Path) -> list[DocumentMetadata]:
    metadata_path = Path(metadata_path)
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    return [DocumentMetadata(**entry) for entry in data]
