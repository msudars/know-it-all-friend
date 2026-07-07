"""RAG answer generation with citations (Phase 9)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

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


def build_prompt(question: str, results: list[SearchResult]) -> str:
    """Assemble the numbered-sources prompt sent to the LLM.

    Kept as a separate function so the exact context an answer was based
    on can be inspected and tested without calling a model.
    """
    blocks = []
    for number, result in enumerate(results, start=1):
        heading = f" > {result.heading}" if result.heading else ""
        blocks.append(f"[{number}] {result.title}{heading} ({result.source_file})\n{result.text}")
    sources_text = "\n\n".join(blocks)
    return f"Sources:\n\n{sources_text}\n\nQuestion: {question}"


def answer_question(
    question: str,
    store: LocalVectorStore,
    embedder: BaseEmbedder,
    llm: BaseLLM,
    top_k: int = 5,
) -> RagAnswer:
    """Answer ``question`` from retrieved context, with source attribution."""
    results = search_index(question, store, embedder, top_k=top_k)
    return answer_from_results(question, results, llm)


def answer_from_results(
    question: str,
    results: list[SearchResult],
    llm: BaseLLM,
) -> RagAnswer:
    """Answer ``question`` from already-retrieved ``results``.

    Split out from :func:`answer_question` so callers that also display the
    retrieved evidence (e.g. the web UI) retrieve once and reuse the results.

    The returned sources are exactly the retrieved chunks, numbered in
    prompt order, so every citation in the answer resolves back to a file.
    If nothing is retrieved, no model call is made and the answer says so.
    """
    if not results:
        return RagAnswer(
            answer="No relevant information was found in the knowledge base.",
            sources=[],
        )

    answer = llm.generate(build_prompt(question, results), system=SYSTEM_PROMPT)
    sources = [
        Source(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            title=r.title,
            source_file=r.source_file,
        )
        for r in results
    ]
    return RagAnswer(answer=answer, sources=sources)
