"""Converter interface for turning source documents into Markdown (Phase 2)."""

from __future__ import annotations

from pathlib import Path


class BaseConverter:
    """Interface every document-to-Markdown converter must implement.

    Callers depend only on this interface, never on a specific backend, so
    new converters (Docling, Marker, Pandoc, custom parsers) can be added
    without changing the conversion pipeline.
    """

    def convert(self, path: str | Path) -> str:
        raise NotImplementedError
