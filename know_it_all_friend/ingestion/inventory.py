"""Document discovery and manifest generation (Phase 1)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# OS bookkeeping files that are never knowledge-base content. Names with a
# colon are NTFS alternate data streams (e.g. `report.pdf:Zone.Identifier`,
# `report.pdf:sec.endpointdlp`) that Windows attaches to downloads and WSL
# exposes as regular files.
_SYSTEM_FILE_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _is_system_file(path: Path) -> bool:
    return path.name in _SYSTEM_FILE_NAMES or ":" in path.name or path.name.startswith(".")


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
    order) keeps the result deterministic across runs and platforms, which
    the sequential IDs in :func:`build_manifest` depend on.

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

    A file that cannot be stat'd (e.g. broken symlink, permission error) is
    logged and skipped rather than aborting the whole scan, matching the
    pipeline-wide rule that one bad file shouldn't block the rest.
    """
    records: list[DocumentRecord] = []
    files = discover_files(input_dir, recursive=recursive, include_system_files=include_system_files)
    for index, file_path in enumerate(files, start=1):
        try:
            size_bytes = file_path.stat().st_size
        except OSError as exc:
            logger.warning("Skipping unreadable file %s: %s", file_path, exc)
            continue

        record = DocumentRecord(
            id=f"document_{index:03d}",
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
