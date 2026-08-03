"""MarkItDown-backed converter -- the first conversion backend (Phase 2 MVP)."""

from __future__ import annotations

from pathlib import Path

from know_it_all_friend.conversion.base import BaseConverter

# Formats that are already text: reading them directly is both the identity
# conversion and an escape from markitdown's encoding sniffing, which guesses
# cp1252 on UTF-8 files and fails the whole document on the first byte it
# can't map.
_TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".text"}


class MarkItDownConverter(BaseConverter):
    """Wraps Microsoft's ``markitdown`` package behind :class:`BaseConverter`.

    The import is deferred to ``__init__`` so that modules which only need
    :class:`BaseConverter` (e.g. tests, type checking) don't pay the cost of
    importing markitdown's dependency tree.
    """

    def __init__(self) -> None:
        from markitdown import MarkItDown

        self._converter = MarkItDown(enable_plugins=False)

    def convert(self, path: str | Path) -> str:
        path = Path(path)
        if path.suffix.lower() in _TEXT_SUFFIXES:
            return path.read_text(encoding="utf-8", errors="replace")
        result = self._converter.convert(str(path))
        return result.text_content
