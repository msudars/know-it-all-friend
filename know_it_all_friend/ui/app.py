"""Streamlit knowledge explorer (Phase 11).

Launch with ``kiaf ui`` (or ``streamlit run know_it_all_friend/ui/app.py``)
from the project root, after building the pipeline outputs in ``storage/``.

The explorer is search-first by design: chat is one panel, and its answers
always appear next to the retrieved evidence they were generated from.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from know_it_all_friend.enrichment.extractor import load_entities
from know_it_all_friend.metadata.extractor import load_metadata
from know_it_all_friend.rag.answer import answer_from_results
from know_it_all_friend.rag.ollama_llm import DEFAULT_CHAT_MODEL, OllamaLLM
from know_it_all_friend.retrieval.search import search_index
from know_it_all_friend.vectorstore.local_store import LocalVectorStore

METADATA_PATH = Path("storage/metadata/documents.json")
ENTITIES_PATH = Path("storage/metadata/entities.json")
INDEX_DIR = Path("storage/indexes/default")

st.set_page_config(page_title="Know-it-all Friend", page_icon="📚", layout="wide")


@st.cache_resource
def _store() -> LocalVectorStore:
    return LocalVectorStore.load(INDEX_DIR)


@st.cache_resource
def _embedder(host: str):
    from know_it_all_friend.embeddings.ollama_embedder import OllamaEmbedder

    return OllamaEmbedder(model=_store().embedding_model, host=host or None)


@st.cache_resource
def _llm(model: str, host: str) -> OllamaLLM:
    return OllamaLLM(model=model, host=host or None)


def _render_result(number: int, result) -> None:
    heading = f" › {result.heading}" if result.heading else ""
    with st.expander(f"[{number}]  {result.score:.3f}  —  {result.title}{heading}"):
        st.caption(f"`{result.source_file}` · `{result.chunk_id}`")
        st.markdown(result.text)


st.title("📚 Know-it-all Friend")

with st.sidebar:
    st.header("Settings")
    top_k = st.slider("Results to retrieve", 1, 20, 5)
    chat_model = st.text_input("Ollama chat model", DEFAULT_CHAT_MODEL)
    ollama_host = st.text_input("Ollama host (blank = local)", "")
    if (INDEX_DIR / "config.json").exists():
        st.success(f"Index: {len(_store())} chunks ({_store().embedding_model})")
    else:
        st.error("No index found. Run the pipeline first:\n`kiaf inventory` → `convert` → "
                 "`metadata` → `chunk` → `index`")

search_tab, ask_tab, documents_tab = st.tabs(["🔍 Search", "💬 Ask", "📄 Documents"])

with search_tab:
    query = st.text_input("Search the knowledge base", placeholder="e.g. Topic A")
    if query:
        if not (INDEX_DIR / "config.json").exists():
            st.error("No index found — build the pipeline outputs first.")
        else:
            with st.spinner("Searching…"):
                results = search_index(query, _store(), _embedder(ollama_host), top_k=top_k)
            if not results:
                st.info("No results.")
            for number, result in enumerate(results, start=1):
                _render_result(number, result)

with ask_tab:
    question = st.text_input("Ask a question", placeholder="What information is available about Topic A?")
    if question:
        if not (INDEX_DIR / "config.json").exists():
            st.error("No index found — build the pipeline outputs first.")
        else:
            with st.spinner("Retrieving context and generating answer…"):
                results = search_index(question, _store(), _embedder(ollama_host), top_k=top_k)
                rag = answer_from_results(question, results, _llm(chat_model, ollama_host))
            answer_col, evidence_col = st.columns(2)
            with answer_col:
                st.subheader("Answer")
                st.markdown(rag.answer)
                if rag.sources:
                    st.caption("Sources")
                    for number, source in enumerate(rag.sources, start=1):
                        st.caption(f"[{number}] {source.title} — `{source.source_file}`")
            with evidence_col:
                st.subheader("Retrieved evidence")
                for number, result in enumerate(results, start=1):
                    _render_result(number, result)

with documents_tab:
    if not METADATA_PATH.exists():
        st.error("No metadata index found. Run `kiaf metadata` first.")
    else:
        docs = load_metadata(METADATA_PATH)
        st.dataframe(
            [
                {
                    "ID": d.document_id,
                    "Title": d.title,
                    "Type": d.extension,
                    "Words": d.word_count,
                    "Source": d.source_file,
                }
                for d in docs
            ],
            use_container_width=True,
        )
        entities_by_id = (
            {e.document_id: e.entities for e in load_entities(ENTITIES_PATH)}
            if ENTITIES_PATH.exists()
            else {}
        )
        selected = st.selectbox("Inspect a document", [d.document_id for d in docs])
        doc = next(d for d in docs if d.document_id == selected)
        if entities_by_id.get(selected):
            st.caption("Extracted entities")
            for entity_type, values in entities_by_id[selected].items():
                if values:
                    st.markdown(f"**{entity_type}**: {', '.join(values)}")
        with st.expander("Converted Markdown", expanded=False):
            markdown_file = Path(doc.markdown_file)
            if markdown_file.exists():
                st.markdown(markdown_file.read_text(encoding="utf-8"))
            else:
                st.warning(f"Markdown file not found: {doc.markdown_file}")
