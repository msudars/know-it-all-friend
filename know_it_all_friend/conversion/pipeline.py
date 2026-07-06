"""Conversion pipeline: turns a document manifest into Markdown files (Phase 2)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from know_it_all_friend.conversion.base import BaseConverter
from know_it_all_friend.ingestion.inventory import DocumentRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversionResult:
    document_id: str
    source_path: str
    markdown_path: str | None
    status: str  # "success" or "failed"
    error: str | None
    timestamp: str


def convert_documents(
    records: list[DocumentRecord],
    converter: BaseConverter,
    output_dir: Path,
) -> list[ConversionResult]:
    """Convert every document in the manifest to Markdown.

    Files are written as ``<document_id>.md`` rather than under their
    original filename: two source files can share a name across different
    input subdirectories, and IDs are guaranteed unique while filenames are
    not. The document ID is still the join key back to the manifest, so
    traceability is preserved.

    A failure on one file is recorded and processing continues with the
    rest of the batch -- a single corrupt or unsupported file must not
    block conversion of the rest of the collection.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[ConversionResult] = []
    for record in records:
        timestamp = datetime.now(timezone.utc).isoformat()
        source_path = Path(record.path)
        markdown_path = output_dir / f"{record.id}.md"

        try:
            markdown_text = converter.convert(source_path)
            markdown_path.write_text(markdown_text, encoding="utf-8")
            logger.info("Converted %s -> %s", source_path, markdown_path)
            results.append(
                ConversionResult(
                    document_id=record.id,
                    source_path=record.path,
                    markdown_path=markdown_path.as_posix(),
                    status="success",
                    error=None,
                    timestamp=timestamp,
                )
            )
        except Exception as exc:  # noqa: BLE001 - must not abort the batch
            logger.error("Failed to convert %s: %s", source_path, exc)
            results.append(
                ConversionResult(
                    document_id=record.id,
                    source_path=record.path,
                    markdown_path=None,
                    status="failed",
                    error=str(exc),
                    timestamp=timestamp,
                )
            )

    return results


def write_conversion_log(results: list[ConversionResult], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    logger.info("Wrote conversion log with %d entries to %s", len(results), output_path)
