"""Metadata extraction: structured records for every converted document (Phase 3)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
    # Defaulted so hand-built fixtures (tests, older callers) don't need to
    # supply them; real documents get both from build_document_metadata.
    content_hash: str = ""
    modified_at: str = ""
    archived: bool = False


def extract_title(markdown_text: str) -> str | None:
    """Return the first ATX heading (any level) in ``markdown_text``, if any.

    Converters can carry source-format line breaks (e.g. vertical tabs from
    PPTX slides) into the heading, so all whitespace runs are collapsed to
    single spaces.
    """
    match = _ATX_HEADING.search(markdown_text)
    if match is None:
        return None
    return " ".join(match.group(1).split())


def _source_modified_at(source_path: str) -> str:
    """Return the source file's modification time as ISO-8601, or "" if unavailable.

    The source file may not exist relative to the current working directory
    (e.g. it was moved, or the manifest was built elsewhere), so this is
    best-effort staleness metadata rather than a hard requirement.
    """
    try:
        mtime = Path(source_path).stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


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
            content_hash=hashlib.sha256(markdown_text.encode("utf-8")).hexdigest(),
            modified_at=_source_modified_at(record.path),
            archived=False,
        )
        docs.append(doc)
        logger.info("Extracted metadata for %s: %r (%d words)", record.id, doc.title, doc.word_count)

    def normalize_name(name: str) -> str:
        return re.sub(r'(_v\d+|-v\d+|_final|-final|\(\d+\)|\s*\d+)$', '', name, flags=re.IGNORECASE).strip()

    seen_hashes: set[str] = set()
    groups: dict[str, list[tuple[int, DocumentMetadata]]] = {}
    
    for i, doc in enumerate(docs):
        # 1. Exact duplicates
        if doc.content_hash in seen_hashes:
            docs[i] = DocumentMetadata(**{**asdict(doc), "archived": True})
            continue
        seen_hashes.add(doc.content_hash)
        
        # 2. Versioning
        norm = normalize_name(Path(doc.source_file).stem)
        groups.setdefault(norm, []).append((i, doc))
        
    for norm, group in groups.items():
        if len(group) > 1:
            group.sort(key=lambda x: x[1].modified_at, reverse=True)
            for i, doc in group[1:]:
                if not doc.archived:
                    docs[i] = DocumentMetadata(**{**asdict(doc), "archived": True})
                    logger.info("Archived older version %s (superceded by %s)", doc.document_id, group[0][1].document_id)

    return docs


def find_changed_documents(
    previous: list[DocumentMetadata], current: list[DocumentMetadata]
) -> list[str]:
    """Return document IDs in ``current`` that are new or whose content changed.

    Compares ``content_hash`` by ``document_id`` against a prior metadata
    snapshot, so callers can detect staleness (e.g. before re-embedding)
    without re-hashing anything themselves.
    """
    previous_hashes = {doc.document_id: doc.content_hash for doc in previous}
    return [
        doc.document_id
        for doc in current
        if previous_hashes.get(doc.document_id) != doc.content_hash
    ]


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
