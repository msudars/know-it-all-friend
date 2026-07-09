"""Retrieval quality evaluation harness."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.retrieval.search import search_index
from know_it_all_friend.vectorstore.local_store import LocalVectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvalCase:
    """A labeled query: the document ID a good retriever should surface."""

    query: str
    expected_document_id: str


@dataclass(frozen=True)
class EvalReport:
    top_k: int
    num_cases: int
    hit_rate: float
    mean_reciprocal_rank: float
    misses: list[str]


def load_eval_cases(path: Path) -> list[EvalCase]:
    """Load eval cases from a JSON file: a list of {"query", "expected_document_id"}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [EvalCase(**entry) for entry in data]


def write_eval_cases(cases: list[EvalCase], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(c) for c in cases], indent=2), encoding="utf-8")


def evaluate_retrieval(
    cases: list[EvalCase],
    store: LocalVectorStore,
    embedder: BaseEmbedder,
    top_k: int = 5,
    **search_kwargs,
) -> EvalReport:
    """Score retrieval against labeled ``(query, expected_document_id)`` cases.

    Hit-rate@k and mean reciprocal rank are the two metrics that matter for a
    single-relevant-document-per-query setup -- each case names one document
    that should appear in the top-k -- which is what a personal document
    collection looks like. Use this to compare configurations (e.g. plain
    vector search vs. hybrid/MMR, passed through ``search_kwargs``)
    objectively instead of guessing.
    """
    if not cases:
        return EvalReport(top_k=top_k, num_cases=0, hit_rate=0.0, mean_reciprocal_rank=0.0, misses=[])

    hits = 0
    reciprocal_ranks: list[float] = []
    misses: list[str] = []
    for case in cases:
        results = search_index(case.query, store, embedder, top_k=top_k, **search_kwargs)
        rank = next(
            (i for i, r in enumerate(results, start=1) if r.document_id == case.expected_document_id),
            None,
        )
        if rank is None:
            reciprocal_ranks.append(0.0)
            misses.append(case.query)
        else:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)

    report = EvalReport(
        top_k=top_k,
        num_cases=len(cases),
        hit_rate=hits / len(cases),
        mean_reciprocal_rank=sum(reciprocal_ranks) / len(cases),
        misses=misses,
    )
    logger.info(
        "Evaluated %d case(s) at top_k=%d: hit_rate=%.2f mrr=%.2f",
        report.num_cases,
        top_k,
        report.hit_rate,
        report.mean_reciprocal_rank,
    )
    return report
