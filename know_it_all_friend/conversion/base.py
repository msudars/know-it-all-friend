"""Converter interface for turning source documents into Markdown (Phase 2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseConverter(ABC):
    """Interface every document-to-Markdown converter must implement.

    Callers depend only on this interface, never on a specific backend, so
    new converters (Docling, Marker, Pandoc, custom parsers) can be added
    without changing the conversion pipeline.
    """

    @abstractmethod
    def convert(self, path: str | Path) -> str: ...
