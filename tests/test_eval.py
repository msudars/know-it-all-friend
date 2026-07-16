from pathlib import Path

from know_it_all_friend.eval.retrieval_eval import (
    EvalCase,
    evaluate_retrieval,
    load_eval_cases,
    write_eval_cases,
)

from tests.conftest import KeywordEmbedder
from tests.test_retrieval import _store


def test_evaluate_retrieval_scores_hits_and_misses() -> None:
    cases = [
        EvalCase(query="tell me about alpha", expected_document_id="document_001"),
        EvalCase(query="gamma and delta", expected_document_id="document_002"),
        EvalCase(query="something unrelated", expected_document_id="document_999"),
    ]

    report = evaluate_retrieval(cases, _store(), KeywordEmbedder(), top_k=2)

    assert report.num_cases == 3
    assert report.hit_rate == 2 / 3
    assert report.misses == ["something unrelated"]
    assert 0.0 < report.mean_reciprocal_rank < 1.0


def test_evaluate_retrieval_empty_cases_returns_zeroed_report() -> None:
    report = evaluate_retrieval([], _store(), KeywordEmbedder())

    assert report.num_cases == 0
    assert report.hit_rate == 0.0
    assert report.mean_reciprocal_rank == 0.0
    assert report.misses == []


def test_eval_cases_roundtrip(tmp_path: Path) -> None:
    cases = [EvalCase(query="alpha", expected_document_id="document_001")]
    path = tmp_path / "cases.json"

    write_eval_cases(cases, path)

    assert load_eval_cases(path) == cases
