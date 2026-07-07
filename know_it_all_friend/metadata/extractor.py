"""Metadata extraction: structured records for every document (Phase 3)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from know_it_all_friend.conversion.pipeline import ConversionResult
from know_it_all_friend.ingestion.inventory import DocumentRecord

logger = logging.getLogger(__name__)

_ATX_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    title: str
    author: str | None
    date: str | None
    source_file: str
    markdown_file: str | None
    extension: str
    size_bytes: int


def extract_title(markdown_text: str) -> str | None:
    """Return the first level-1 ATX heading in ``markdown_text``, if any."""
    match = _ATX_H1.search(markdown_text)
    return match.group(1) if match else None


def _source_date(source_path: Path) -> str | None:
    """Return the source file's modification date (ISO format).

    This is only a baseline: many converters don't expose document-level
    dates, and the filesystem mtime is the one signal available for every
    file. Richer extraction belongs to the enrichment phase.
    """
    try:
        mtime = source_path.stat().st_mtime
    except OSError as exc:
        logger.warning("Could not stat %s for date extraction: %s", source_path, exc)
        return None
    return datetime.fromtimestamp(mtime, tz=timezone.utc).date().isoformat()


def build_metadata(
    records: list[DocumentRecord],
    conversion_results: list[ConversionResult],
) -> list[DocumentMetadata]:
    """Join the manifest with the conversion log and extract basic metadata.

    The document ID is the join key. A record without a successful
    conversion still gets a metadata entry (with ``markdown_file=None``) so
    the index covers the whole collection, and an unreadable Markdown file
    is logged and treated as empty rather than aborting the batch.

    The ``author`` field is a schema slot only: content-based extraction of
    authors, topics, and entities is deferred to knowledge enrichment
    (Phase 4).
    """
    markdown_by_id = {
        result.document_id: result.markdown_path
        for result in conversion_results
        if result.status == "success" and result.markdown_path
    }

    metadata: list[DocumentMetadata] = []
    for record in records:
        markdown_file = markdown_by_id.get(record.id)

        title: str | None = None
        if markdown_file is not None:
            try:
                title = extract_title(Path(markdown_file).read_text(encoding="utf-8"))
            except OSError as exc:
                logger.warning("Could not read %s for title extraction: %s", markdown_file, exc)
        if title is None:
            title = Path(record.filename).stem

        entry = DocumentMetadata(
            document_id=record.id,
            title=title,
            author=None,
            date=_source_date(Path(record.path)),
            source_file=record.path,
            markdown_file=markdown_file,
            extension=record.extension,
            size_bytes=record.size_bytes,
        )
        metadata.append(entry)
        logger.info("Extracted metadata for %s: %r", record.id, entry.title)

    return metadata


def write_metadata_index(metadata: list[DocumentMetadata], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(m) for m in metadata], f, indent=2)
    logger.info("Wrote metadata index with %d entries to %s", len(metadata), output_path)
