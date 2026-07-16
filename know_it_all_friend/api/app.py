"""REST API over the knowledge base (Phase 11).

Backends are injectable so the app can be tested (and reused) without an
Ollama server; when not injected, they are created lazily from the on-disk
index so the API can start before `kiaf index` has run.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from know_it_all_friend.embeddings.base import BaseEmbedder
from know_it_all_friend.metadata.extractor import load_metadata
from know_it_all_friend.rag.answer import answer_question
from know_it_all_friend.rag.base import BaseLLM
from know_it_all_friend.retrieval.search import search_index
from know_it_all_friend.vectorstore.local_store import LocalVectorStore

logger = logging.getLogger(__name__)

DEFAULT_METADATA_PATH = Path("storage/metadata/documents.json")
DEFAULT_INDEX_DIR = Path("storage/indexes/default")


class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    start_date: str | None = None
    end_date: str | None = None


DEFAULT_ENTITIES_PATH = Path("storage/metadata/entities.json")

def create_app(
    metadata_path: Path = DEFAULT_METADATA_PATH,
    entities_path: Path = DEFAULT_ENTITIES_PATH,
    index_dir: Path = DEFAULT_INDEX_DIR,
    store: LocalVectorStore | None = None,
    embedder: BaseEmbedder | None = None,
    llm: BaseLLM | None = None,
    ollama_host: str | None = None,
    chat_model: str | None = None,
) -> FastAPI:
    """Build the API app, wiring injected backends or lazy Ollama defaults."""
    app = FastAPI(
        title="Know-it-all Friend",
        description="Search, inspect, and question a document knowledge base.",
    )
    state: dict = {"store": store, "embedder": embedder, "llm": llm}

    def get_store() -> LocalVectorStore:
        if state["store"] is None:
            if not (Path(index_dir) / "config.json").exists():
                raise HTTPException(
                    status_code=503, detail=f"No index at {index_dir}; run `kiaf index` first."
                )
            state["store"] = LocalVectorStore.load(index_dir)
        return state["store"]

    def get_embedder() -> BaseEmbedder:
        if state["embedder"] is None:
            from know_it_all_friend.embeddings.ollama_embedder import OllamaEmbedder

            state["embedder"] = OllamaEmbedder(model=get_store().embedding_model, host=ollama_host)
        return state["embedder"]

    def get_llm() -> BaseLLM:
        if state["llm"] is None:
            from know_it_all_friend.rag.ollama_llm import DEFAULT_CHAT_MODEL, OllamaLLM

            state["llm"] = OllamaLLM(model=chat_model or DEFAULT_CHAT_MODEL, host=ollama_host)
        return state["llm"]

    def _get_date_filter(start_date: str | None, end_date: str | None) -> set[str] | None:
        if not start_date and not end_date:
            return None
        from know_it_all_friend.enrichment.extractor import load_entities
        if "entities" not in state:
            if not Path(entities_path).exists():
                state["entities"] = []
            else:
                state["entities"] = load_entities(entities_path)
        
        valid = set()
        for e in state["entities"]:
            date = getattr(e, "document_date", "")
            if not date:
                continue
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue
            valid.add(e.document_id)
        return valid

    from fastapi.responses import RedirectResponse

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/documents")
    def documents() -> list[dict]:
        if not Path(metadata_path).exists():
            raise HTTPException(
                status_code=503, detail=f"No metadata at {metadata_path}; run `kiaf metadata` first."
            )
        return [asdict(d) for d in load_metadata(metadata_path)]

    @app.get("/search")
    def search(
        q: str = Query(..., min_length=1, description="Natural-language search query."),
        top_k: int = Query(5, ge=1, le=50),
        start_date: str | None = Query(None, description="Filter by document date (YYYY-MM-DD)."),
        end_date: str | None = Query(None, description="Filter by document date (YYYY-MM-DD)."),
    ) -> list[dict]:
        filter_ids = _get_date_filter(start_date, end_date)
        results = search_index(q, get_store(), get_embedder(), top_k=top_k, filter_document_ids=filter_ids)
        return [asdict(r) for r in results]

    @app.post("/ask")
    def ask(request: AskRequest) -> dict:
        filter_ids = _get_date_filter(request.start_date, request.end_date)
        result = answer_question(
            request.question, get_store(), get_embedder(), get_llm(), top_k=request.top_k, filter_document_ids=filter_ids
        )
        return {"answer": result.answer, "sources": [asdict(s) for s in result.sources]}

    return app
