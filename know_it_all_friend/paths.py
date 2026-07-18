"""Where kiaf keeps its pipeline outputs, resolved once at import time.

Resolution order:

1. ``KIAF_HOME`` environment variable, if set.
2. ``./storage`` if it already exists (the original repo-clone layout).
3. ``~/.kiaf`` — the default for installed usage, so ``kiaf`` works from any directory.
"""

from __future__ import annotations

import os
from pathlib import Path


def storage_root() -> Path:
    env = os.environ.get("KIAF_HOME")
    if env:
        return Path(env).expanduser()
    local = Path("storage")
    if local.is_dir():
        return local
    return Path.home() / ".kiaf"


_ROOT = storage_root()

MANIFEST = _ROOT / "metadata" / "manifest.json"
CONVERSION_LOG = _ROOT / "metadata" / "conversion_log.json"
DOCUMENTS = _ROOT / "metadata" / "documents.json"
ENTITIES = _ROOT / "metadata" / "entities.json"
GRAPH = _ROOT / "metadata" / "graph.json"
CHUNKS = _ROOT / "chunks" / "chunks.json"
MARKDOWN_DIR = _ROOT / "markdown"
INDEX_DIR = _ROOT / "indexes" / "default"
