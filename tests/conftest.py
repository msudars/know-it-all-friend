"""Shared test fixtures and helper classes.

Centralises the fake backends and factory functions that multiple test
modules need, so changes to an interface only require one update.
"""

from __future__ import annotations

import pytest

from know_it_all_friend.chunking.chunker import Chunk
from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.rag.base import BaseLLM
from know_it_all_friend.retrieval.search import SearchResult


# ---------------------------------------------------------------------------
# Fake embedders
# ---------------------------------------------------------------------------

VOCAB = ["alpha", "beta", "gamma", "delta"]


class BagOfWordsEmbedder(BaseEmbedder):
    """Deterministic embedder: counts vocabulary words for testable ranking."""

    model = "bag-of-words-test"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(text.lower().split().count(word)) for word in VOCAB]
            for text in texts
        ]


class KeywordEmbedder(BaseEmbedder):
    """Deterministic embedder using substring counts (more sensitive than BagOfWords)."""

    model = "keyword-test-embedder"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(text.lower().count(word)) for word in VOCAB] for text in texts]


# ---------------------------------------------------------------------------
# Fake LLMs
# ---------------------------------------------------------------------------


class CannedLLM(BaseLLM):
    """Returns a fixed reply, optionally records prompts."""

    model = "canned-test"

    def __init__(self, reply: str = "Canned answer [1]."):
        self.reply = reply
        self.prompts: list[str] = []
        self.systems: list[str | None] = []

    def generate(self, prompt: str, system: str | None = None) -> str:
        self.prompts.append(prompt)
        self.systems.append(system)
        return self.reply


class ScriptedLLM(BaseLLM):
    """Returns a fixed answer with streaming support."""

    model = "scripted-test"

    def __init__(self, answer: str):
        self._answer = answer

    def generate(self, prompt: str, system: str | None = None) -> str:
        return self._answer

    from typing import Iterator

    def generate_stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        midpoint = len(self._answer) // 2
        yield self._answer[:midpoint]
        yield self._answer[midpoint:]


class FailingLLM(BaseLLM):
    """Always raises RuntimeError."""

    model = "failing-test"

    def generate(self, prompt: str, system: str | None = None) -> str:
        raise RuntimeError("simulated model failure")


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_chunk(
    chunk_id: str,
    text: str,
    document_id: str | None = None,
    title: str = "Example Report",
    source_file: str = "input/report.txt",
    heading: str | None = "Section",
) -> Chunk:
    """Build a Chunk with sensible defaults for testing."""
    if document_id is None:
        document_id = chunk_id.rsplit("_chunk_", 1)[0] if "_chunk_" in chunk_id else "document_001"
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        title=title,
        source_file=source_file,
        heading=heading,
        text=text,
    )


def make_result(
    chunk_id: str,
    text: str,
    document_id: str = "document_001",
    title: str = "Example Report",
    source_file: str = "input/report.txt",
    heading: str = "Section",
    score: float = 0.9,
) -> SearchResult:
    """Build a SearchResult with sensible defaults for testing."""
    return SearchResult(
        chunk_id=chunk_id,
        document_id=document_id,
        title=title,
        source_file=source_file,
        heading=heading,
        text=text,
        score=score,
    )
