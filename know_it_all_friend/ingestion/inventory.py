"""Document discovery and manifest generation (Phase 1)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_ID_MAX_CHARS = 60
_NON_SLUG = re.compile(r"[^a-z0-9]+")

# OS bookkeeping files that are never knowledge-base content. Names with a
# colon are NTFS alternate data streams (e.g. `report.pdf:Zone.Identifier`,
# `report.pdf:sec.endpointdlp`) that Windows attaches to downloads and WSL
# exposes as regular files.
_SYSTEM_FILE_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _is_system_file(path: Path) -> bool:
    return path.name in _SYSTEM_FILE_NAMES or ":" in path.name or path.name.startswith(".")


def _document_id(relative_path: Path, taken: set[str]) -> str:
    """Derive a stable, readable, filesystem-safe document ID from a relative path.

    IDs are derived from the path rather than the file's position in the scan
    so that adding or removing one document doesn't renumber every document
    after it -- positional IDs silently invalidate stored citations, cached
    per-document work, and the `<document_id>.md` files on disk.

    The slug is truncated for sane filenames, so two long paths can collide;
    a short digest of the full path disambiguates. The digest is appended
    only on collision, keeping the common case readable.
    """
    slug = _NON_SLUG.sub("_", relative_path.as_posix().lower()).strip("_")[:_ID_MAX_CHARS]
    candidate = slug or "document"
    if candidate in taken:
        digest = hashlib.sha1(relative_path.as_posix().encode("utf-8")).hexdigest()[:8]
        candidate = f"{candidate}_{digest}"
    taken.add(candidate)
    return candidate


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    filename: str
    extension: str
    path: str
    size_bytes: int


def discover_files(
    input_dir: Path,
    recursive: bool = True,
    include_system_files: bool = False,
) -> list[Path]:
    """Return every file under ``input_dir``, sorted by relative path.

    Sorting by relative path (rather than relying on filesystem traversal
    order) keeps manifest order deterministic across runs and platforms.

    Hidden dotfiles, OS bookkeeping files, and NTFS alternate-data-stream
    sidecars are excluded unless ``include_system_files`` is set.
    """
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory does not exist: {input_dir}")

    pattern = "**/*" if recursive else "*"
    files = []
    for path in input_dir.glob(pattern):
        if not path.is_file():
            continue
        if not include_system_files and _is_system_file(path):
            logger.info("Excluding system file %s", path)
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(input_dir).as_posix())


def build_manifest(
    input_dir: Path,
    recursive: bool = True,
    include_system_files: bool = False,
) -> list[DocumentRecord]:
    """Scan ``input_dir`` and build a manifest of :class:`DocumentRecord`.

    IDs are derived from each file's path (see :func:`_document_id`), so a
    given document keeps its ID as the collection grows and shrinks.

    A file that cannot be stat'd (e.g. broken symlink, permission error) is
    logged and skipped rather than aborting the whole scan, matching the
    pipeline-wide rule that one bad file shouldn't block the rest.
    """
    input_dir = Path(input_dir)
    records: list[DocumentRecord] = []
    taken: set[str] = set()
    files = discover_files(input_dir, recursive=recursive, include_system_files=include_system_files)
    for file_path in files:
        try:
            size_bytes = file_path.stat().st_size
        except OSError as exc:
            logger.warning("Skipping unreadable file %s: %s", file_path, exc)
            continue

        record = DocumentRecord(
            id=_document_id(file_path.relative_to(input_dir), taken),
            filename=file_path.name,
            extension=file_path.suffix.lstrip(".").lower(),
            path=file_path.as_posix(),
            size_bytes=size_bytes,
        )
        records.append(record)
        logger.info("Discovered %s (%s, %d bytes)", record.filename, record.id, record.size_bytes)

    return records


def write_manifest(records: list[DocumentRecord], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, indent=2)
    logger.info("Wrote manifest with %d entries to %s", len(records), output_path)
