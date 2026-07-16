"""RAG answer generation with citations (Phase 9)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.rag.base import BaseLLM
from know_it_all_friend.retrieval.search import SearchResult, search_index
from know_it_all_friend.vectorstore.local_store import LocalVectorStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You answer questions using only the numbered sources provided. "
    "Cite sources inline as [1], [2], etc. after the statements they support. "
    "If the sources do not contain the answer, say so plainly instead of guessing."
)

DEFAULT_MAX_CONTEXT_CHARS = 8000

_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class Source:
    chunk_id: str
    document_id: str
    title: str
    source_file: str


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    sources: list[Source]
    invalid_citations: list[int] = field(default_factory=list)


def build_prompt(
    question: str,
    results: list[SearchResult],
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str:
    """Assemble the numbered-sources prompt sent to the LLM.

    Kept as a separate function so the exact context an answer was based
    on can be inspected and tested without calling a model.

    Sources are added in score order (``results`` is already ranked) until
    ``max_context_chars`` would be exceeded; remaining lower-ranked sources
    are dropped rather than truncated mid-chunk, which otherwise silently
    overflows the model's context window on a large ``top_k``. The highest
    ranked source is always included even if it alone exceeds the budget.
    """
    blocks: list[str] = []
    used_chars = 0
    for number, result in enumerate(results, start=1):
        heading = f" > {result.heading}" if result.heading else ""
        block = f"[{number}] {result.title}{heading} ({result.source_file})\n{result.text}"
        if blocks and used_chars + len(block) > max_context_chars:
            break
        blocks.append(block)
        used_chars += len(block)

    dropped = len(results) - len(blocks)
    if dropped:
        logger.info("Dropped %d lower-ranked source(s) to stay within max_context_chars=%d", dropped, max_context_chars)

    sources_text = "\n\n".join(blocks)
    return f"Sources:\n\n{sources_text}\n\nQuestion: {question}"


def validate_citations(answer: str, num_sources: int) -> list[int]:
    """Return any inline ``[n]`` citation numbers in ``answer`` outside ``1..num_sources``.

    A non-empty result is a signal the model may have hallucinated or
    misnumbered a citation; this only reports it, it doesn't rewrite the
    answer.
    """
    cited = {int(n) for n in _CITATION_RE.findall(answer)}
    return sorted(n for n in cited if n < 1 or n > num_sources)


def _sources_from_results(results: list[SearchResult]) -> list[Source]:
    return [
        Source(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            title=r.title,
            source_file=r.source_file,
        )
        for r in results
    ]


def answer_question(
    question: str,
    store: LocalVectorStore,
    embedder: BaseEmbedder,
    llm: BaseLLM,
    top_k: int = 5,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    filter_document_ids: set[str] | None = None,
) -> RagAnswer:
    """Answer ``question`` from retrieved context, with source attribution."""
    results = search_index(question, store, embedder, top_k=top_k, filter_document_ids=filter_document_ids)
    return answer_from_results(question, results, llm, max_context_chars=max_context_chars)


def answer_from_results(
    question: str,
    results: list[SearchResult],
    llm: BaseLLM,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> RagAnswer:
    """Answer ``question`` from already-retrieved ``results``.

    Split out from :func:`answer_question` so callers that also display the
    retrieved evidence (e.g. the web UI) retrieve once and reuse the results.

    The returned sources are exactly the retrieved chunks, numbered in
    prompt order, so every citation in the answer resolves back to a file.
    If nothing is retrieved, no model call is made and the answer says so.
    """
    if not results:
        return RagAnswer( # type: ignore[return-value]

            answer="No relevant information was found in the knowledge base.",
            sources=[],
        )

    prompt = build_prompt(question, results, max_context_chars=max_context_chars)
    answer = llm.generate(prompt, system=SYSTEM_PROMPT)
    invalid_citations = validate_citations(answer, len(results))
    if invalid_citations:
        logger.warning("Answer to %r cites out-of-range source(s): %s", question, invalid_citations)
    return RagAnswer( # type: ignore[return-value]

        answer=answer,
        sources=_sources_from_results(results),
        invalid_citations=invalid_citations,
    )


from typing import Generator
def answer_question_stream(
    question: str,
    store: LocalVectorStore,
    embedder: BaseEmbedder,
    llm: BaseLLM,
    top_k: int = 5,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> Iterator[str]:
    """Like :func:`answer_question`, but yields the answer text incrementally.

    Yields chunks of the answer as they arrive from the LLM. Once the
    generator is exhausted, its return value -- available via
    ``StopIteration.value`` when driven manually, or as the trailing value of
    a ``yield from`` -- is the final :class:`RagAnswer`, same as the
    non-streaming variant.
    """
    results = search_index(question, store, embedder, top_k=top_k)
    if not results:
        answer = "No relevant information was found in the knowledge base."
        yield answer
        return RagAnswer( # type: ignore[return-value]
answer=answer, sources=[])

    prompt = build_prompt(question, results, max_context_chars=max_context_chars)
    pieces: list[str] = []
    for piece in llm.generate_stream(prompt, system=SYSTEM_PROMPT):
        pieces.append(piece)
        yield piece

    answer = "".join(pieces)
    invalid_citations = validate_citations(answer, len(results))
    if invalid_citations:
        logger.warning("Answer to %r cites out-of-range source(s): %s", question, invalid_citations)
    return RagAnswer( # type: ignore[return-value]

        answer=answer,
        sources=_sources_from_results(results),
        invalid_citations=invalid_citations,
    )
