from know_it_all_friend.chunking.chunker import Chunk
from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.rag.answer import answer_question, build_prompt
from know_it_all_friend.rag.base import BaseLLM
from know_it_all_friend.retrieval.search import SearchResult
from know_it_all_friend.vectorstore.local_store import build_index


class BagOfWordsEmbedder(BaseEmbedder):
    model = "bag-of-words-test"
    _vocabulary = ["alpha", "beta", "gamma", "delta"]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(text.lower().split().count(word)) for word in self._vocabulary]
            for text in texts
        ]


class RecordingLLM(BaseLLM):
    """Echoes a canned answer while recording the prompt it was given."""

    model = "recording-test"

    def __init__(self):
        self.prompts: list[str] = []
        self.systems: list[str | None] = []

    def generate(self, prompt: str, system: str | None = None) -> str:
        self.prompts.append(prompt)
        self.systems.append(system)
        return "Canned answer [1]."


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="document_001",
        title="Example Report",
        source_file="input/report.txt",
        heading="Section",
        text=text,
    )


def _result(chunk_id: str, text: str) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id="document_001",
        title="Example Report",
        source_file="input/report.txt",
        heading="Section",
        text=text,
        score=0.9,
    )


def test_build_prompt_numbers_sources_and_includes_question() -> None:
    prompt = build_prompt("What is alpha?", [_result("c1", "alpha facts"), _result("c2", "more")])

    assert "[1] Example Report > Section (input/report.txt)\nalpha facts" in prompt
    assert "[2] Example Report" in prompt
    assert prompt.endswith("Question: What is alpha?")


def test_answer_question_returns_answer_with_sources() -> None:
    store = build_index([_chunk("c1", "alpha facts"), _chunk("c2", "beta facts")], BagOfWordsEmbedder())
    llm = RecordingLLM()

    result = answer_question("alpha", store, BagOfWordsEmbedder(), llm, top_k=1)

    assert result.answer == "Canned answer [1]."
    assert [s.chunk_id for s in result.sources] == ["c1"]
    assert result.sources[0].source_file == "input/report.txt"
    assert "alpha facts" in llm.prompts[0]
    assert llm.systems[0] is not None


def test_answer_question_with_empty_index_skips_the_model() -> None:
    store = build_index([], BagOfWordsEmbedder())
    llm = RecordingLLM()

    result = answer_question("anything", store, BagOfWordsEmbedder(), llm)

    assert result.sources == []
    assert "No relevant information" in result.answer
    assert llm.prompts == []
