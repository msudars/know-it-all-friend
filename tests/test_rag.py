from know_it_all_friend.rag.answer import (
    answer_question,
    answer_question_stream,
    build_prompt,
    validate_citations,
)
from know_it_all_friend.vectorstore.local_store import build_index
from tests.conftest import BagOfWordsEmbedder, CannedLLM, ScriptedLLM, make_chunk, make_result


def test_build_prompt_numbers_sources_and_includes_question() -> None:
    prompt = build_prompt("What is alpha?", [make_result("c1", "alpha facts"), make_result("c2", "more")])

    assert "[1] Example Report > Section (input/report.txt)\nalpha facts" in prompt
    assert "[2] Example Report" in prompt
    assert prompt.endswith("Question: What is alpha?")


def test_answer_question_returns_answer_with_sources() -> None:
    store = build_index([make_chunk("c1", "alpha facts"), make_chunk("c2", "beta facts")], BagOfWordsEmbedder())
    llm = CannedLLM()

    result = answer_question("alpha", store, BagOfWordsEmbedder(), llm, top_k=1)

    assert result.answer == "Canned answer [1]."
    assert [s.chunk_id for s in result.sources] == ["c1"]
    assert result.sources[0].source_file == "input/report.txt"
    assert "alpha facts" in llm.prompts[0]
    assert llm.systems[0] is not None


def test_answer_question_with_empty_index_skips_the_model() -> None:
    store = build_index([], BagOfWordsEmbedder())
    llm = CannedLLM()

    result = answer_question("anything", store, BagOfWordsEmbedder(), llm)

    assert result.sources == []
    assert "No relevant information" in result.answer
    assert llm.prompts == []


def test_build_prompt_drops_lower_ranked_sources_beyond_budget() -> None:
    results = [make_result("c1", "a" * 50), make_result("c2", "b" * 50), make_result("c3", "c" * 50)]

    prompt = build_prompt("question", results, max_context_chars=80)

    assert "[1]" in prompt
    assert "[2]" not in prompt
    assert "[3]" not in prompt


def test_build_prompt_always_includes_first_source_even_over_budget() -> None:
    results = [make_result("c1", "a" * 500)]

    prompt = build_prompt("question", results, max_context_chars=10)

    assert "[1]" in prompt


def test_validate_citations_flags_out_of_range_numbers() -> None:
    assert validate_citations("supported by [1] and [3]", num_sources=2) == [3]
    assert validate_citations("supported by [1] and [2]", num_sources=2) == []


def test_answer_question_flags_invalid_citations() -> None:
    store = build_index([make_chunk("c1", "alpha facts")], BagOfWordsEmbedder())
    llm = ScriptedLLM("Answer citing [5].")

    result = answer_question("alpha", store, BagOfWordsEmbedder(), llm, top_k=1)

    assert result.invalid_citations == [5]


def test_answer_question_stream_yields_pieces_and_returns_final_answer() -> None:
    store = build_index([make_chunk("c1", "alpha facts")], BagOfWordsEmbedder())
    llm = ScriptedLLM("Streamed answer [1].")

    generator = answer_question_stream("alpha", store, BagOfWordsEmbedder(), llm, top_k=1)
    pieces = []
    result = None
    try:
        while True:
            pieces.append(next(generator))
    except StopIteration as stop:
        result = stop.value

    assert "".join(pieces) == "Streamed answer [1]."
    assert result.answer == "Streamed answer [1]."
    assert [s.chunk_id for s in result.sources] == ["c1"]
    assert result.invalid_citations == []
