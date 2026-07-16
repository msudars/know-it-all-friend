"""Command-line entry point for Know-it-all Friend (``kiaf``)."""

from __future__ import annotations

import json
import logging
import typing
from pathlib import Path

import typer

app = typer.Typer(help="Know-it-all Friend: turn document collections into a knowledge base.")
graph_app = typer.Typer(help="Build and explore the knowledge graph (Phase 12).")
app.add_typer(graph_app, name="graph")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def inventory(
    input_dir: Path = typer.Argument(..., help="Directory of source documents to scan."),
    output: Path = typer.Option(
        Path("storage/metadata/manifest.json"), "--output", "-o", help="Where to write the manifest."
    ),
    recursive: bool = typer.Option(True, help="Recurse into subdirectories."),
    include_system_files: bool = typer.Option(
        False, help="Also inventory hidden/OS bookkeeping files and NTFS sidecar streams."
    ),
) -> None:
    """Scan a directory and write a document manifest (Phase 1)."""
    from know_it_all_friend.ingestion.inventory import build_manifest, write_manifest

    records = build_manifest(input_dir, recursive=recursive, include_system_files=include_system_files)
    write_manifest(records, output)
    typer.echo(f"Discovered {len(records)} document(s). Manifest written to {output}")


@app.command()
def convert(
    manifest: Path = typer.Option(
        Path("storage/metadata/manifest.json"), "--manifest", "-m", help="Manifest produced by `kiaf inventory`."
    ),
    output: Path = typer.Option(
        Path("storage/markdown"), "--output", "-o", help="Directory to write converted Markdown files."
    ),
    log: Path = typer.Option(
        Path("storage/metadata/conversion_log.json"), "--log", help="Where to write the conversion status log."
    ),
) -> None:
    """Convert every document in a manifest to Markdown (Phase 2)."""
    from know_it_all_friend.conversion.markitdown_converter import MarkItDownConverter
    from know_it_all_friend.conversion.pipeline import convert_documents, write_conversion_log
    from know_it_all_friend.ingestion.inventory import DocumentRecord

    records = [DocumentRecord(**r) for r in json.loads(manifest.read_text(encoding="utf-8"))]
    converter = MarkItDownConverter()
    results = convert_documents(records, converter, output)
    write_conversion_log(results, log)

    succeeded = sum(1 for r in results if r.status == "success")
    failed = len(results) - succeeded
    typer.echo(f"Converted {succeeded} document(s), {failed} failed. Log written to {log}")


@app.command()
def metadata(
    manifest: Path = typer.Option(
        Path("storage/metadata/manifest.json"), "--manifest", "-m", help="Manifest produced by `kiaf inventory`."
    ),
    log: Path = typer.Option(
        Path("storage/metadata/conversion_log.json"), "--log", help="Conversion log produced by `kiaf convert`."
    ),
    output: Path = typer.Option(
        Path("storage/metadata/documents.json"), "--output", "-o", help="Where to write the metadata index."
    ),
) -> None:
    """Extract per-document metadata from converted Markdown (Phase 3)."""
    from know_it_all_friend.ingestion.inventory import DocumentRecord
    from know_it_all_friend.metadata.extractor import build_document_metadata, write_metadata

    records = [DocumentRecord(**r) for r in json.loads(manifest.read_text(encoding="utf-8"))]
    conversion_log = json.loads(log.read_text(encoding="utf-8"))
    docs = build_document_metadata(records, conversion_log)
    write_metadata(docs, output)
    typer.echo(f"Extracted metadata for {len(docs)} document(s). Written to {output}")


@app.command()
def enrich(
    metadata_file: Path = typer.Option(
        Path("storage/metadata/documents.json"), "--metadata", help="Metadata index produced by `kiaf metadata`."
    ),
    output: Path = typer.Option(
        Path("storage/metadata/entities.json"), "--output", "-o", help="Where to write the extracted entities."
    ),
    model: str = typer.Option("llama3.2", help="Ollama chat model for entity extraction."),  # keep in sync with rag.ollama_llm.DEFAULT_CHAT_MODEL
    max_chars: int = typer.Option(
        8000, help="How much of each document to send to the model."  # keep in sync with enrichment.extractor.DEFAULT_MAX_CHARS
    ),
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Extract entities and topics from each document (Phase 4)."""
    from know_it_all_friend.enrichment.extractor import enrich_documents, write_entities
    from know_it_all_friend.metadata.extractor import load_metadata
    from know_it_all_friend.rag.ollama_llm import OllamaLLM

    docs = load_metadata(metadata_file)
    llm = OllamaLLM(model=model, host=host)
    enriched = enrich_documents(docs, llm, max_chars=max_chars)
    write_entities(enriched, output)
    typer.echo(
        f"Enriched {len(enriched)}/{len(docs)} document(s) with {model}. Written to {output}"
    )


@app.command()
def chunk(
    metadata_file: Path = typer.Option(
        Path("storage/metadata/documents.json"), "--metadata", help="Metadata index produced by `kiaf metadata`."
    ),
    output: Path = typer.Option(
        Path("storage/chunks/chunks.json"), "--output", "-o", help="Where to write the chunks."
    ),
    max_chars: int = typer.Option(1500, help="Maximum characters per chunk."),  # keep in sync with chunking.chunker.DEFAULT_MAX_CHARS
    overlap_chars: int = typer.Option(
        200, help="Characters of trailing context carried into the next chunk."  # keep in sync with chunking.chunker.DEFAULT_OVERLAP_CHARS
    ),
) -> None:
    """Split Markdown documents into retrievable chunks (Phase 5)."""
    from know_it_all_friend.chunking.chunker import chunk_documents, write_chunks
    from know_it_all_friend.metadata.extractor import load_metadata

    docs = load_metadata(metadata_file)
    chunks = chunk_documents(docs, max_chars=max_chars, overlap_chars=overlap_chars)
    write_chunks(chunks, output)
    typer.echo(f"Created {len(chunks)} chunk(s) from {len(docs)} document(s). Written to {output}")


@app.command()
def index(
    chunks_file: Path = typer.Option(
        Path("storage/chunks/chunks.json"), "--chunks", help="Chunks produced by `kiaf chunk`."
    ),
    output: Path = typer.Option(
        Path("storage/indexes/default"), "--output", "-o", help="Directory to write the vector index."
    ),
    embed_model: str = typer.Option("nomic-embed-text", help="Ollama embedding model to use."),  # keep in sync with embeddings.ollama_embedder.DEFAULT_EMBED_MODEL
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Embed chunks with a local Ollama model and build the vector index (Phases 6-7)."""
    from know_it_all_friend.chunking.chunker import load_chunks
    from know_it_all_friend.embeddings.ollama_embedder import OllamaEmbedder
    from know_it_all_friend.vectorstore.local_store import build_index

    chunks = load_chunks(chunks_file)
    embedder = OllamaEmbedder(model=embed_model, host=host)
    store = build_index(chunks, embedder)
    store.save(output)
    typer.echo(f"Indexed {len(store)} chunk(s) with {embed_model}. Index written to {output}")


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural-language search query."),
    index_dir: Path = typer.Option(
        Path("storage/indexes/default"), "--index", help="Index directory produced by `kiaf index`."
    ),
    top_k: int = typer.Option(5, help="Number of results to return."),
    mode: str = typer.Option(
        "vector", help="'vector' for pure cosine search, 'hybrid' to fuse in BM25 keyword search."
    ),
    alpha: float = typer.Option(0.5, help="Hybrid mode only: RRF weight toward vector vs. keyword."),
    score_threshold: float = typer.Option(
        None, help="Drop results below this score instead of always returning top_k."
    ),
    diversify: bool = typer.Option(
        False, help="Re-select results with MMR so near-duplicate chunks don't crowd out distinct ones."
    ),
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Semantic search over the indexed chunks (Phase 8)."""
    from know_it_all_friend.embeddings.ollama_embedder import OllamaEmbedder
    from know_it_all_friend.retrieval.search import search_index
    from know_it_all_friend.vectorstore.local_store import LocalVectorStore

    store = LocalVectorStore.load(index_dir)
    embedder = OllamaEmbedder(model=store.embedding_model, host=host)
    results = search_index(
        query,
        store,
        embedder,
        top_k=top_k,
        mode=typing.cast(typing.Literal["vector", "hybrid"], mode),
        alpha=alpha,
        score_threshold=score_threshold,
        diversify=diversify,
    )

    if not results:
        typer.echo("No results (is the index empty?).")
        return
    for number, result in enumerate(results, start=1):
        heading = f" > {result.heading}" if result.heading else ""
        typer.echo(f"\n[{number}] {result.score:.3f}  {result.title}{heading}")
        typer.echo(f"    {result.source_file} ({result.chunk_id})")
        snippet = " ".join(result.text.split())
        typer.echo(f"    {snippet[:200]}{'...' if len(snippet) > 200 else ''}")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to answer from the document collection."),
    index_dir: Path = typer.Option(
        Path("storage/indexes/default"), "--index", help="Index directory produced by `kiaf index`."
    ),
    model: str = typer.Option("llama3.2", help="Ollama chat model to generate the answer."),  # keep in sync with rag.ollama_llm.DEFAULT_CHAT_MODEL
    top_k: int = typer.Option(5, help="Number of chunks to retrieve as context."),
    stream: bool = typer.Option(False, help="Print the answer incrementally as it's generated."),
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Answer a question from retrieved context, with citations (Phase 9)."""
    from know_it_all_friend.embeddings.ollama_embedder import OllamaEmbedder
    from know_it_all_friend.rag.answer import answer_question, answer_question_stream
    from know_it_all_friend.rag.ollama_llm import OllamaLLM
    from know_it_all_friend.vectorstore.local_store import LocalVectorStore

    store = LocalVectorStore.load(index_dir)
    embedder = OllamaEmbedder(model=store.embedding_model, host=host)
    llm = OllamaLLM(model=model, host=host)

    if stream:
        typer.echo()
        generator = answer_question_stream(question, store, embedder, llm, top_k=top_k)
        result = None
        try:
            while True:
                typer.echo(next(generator), nl=False)
        except StopIteration as stop:
            result = stop.value
        typer.echo("\n")
    else:
        result = answer_question(question, store, embedder, llm, top_k=top_k)
        typer.echo(f"\n{result.answer}\n")

    if result.invalid_citations:
        typer.echo(f"Warning: answer cites out-of-range source(s): {result.invalid_citations}")
    if result.sources:
        typer.echo("Sources:")
        for number, source in enumerate(result.sources, start=1):
            typer.echo(f"  [{number}] {source.title} — {source.source_file} ({source.chunk_id})")


@app.command("eval-retrieval")
def eval_retrieval(
    cases_file: Path = typer.Argument(
        ..., help='JSON file of eval cases: [{"query": "...", "expected_document_id": "document_001"}, ...]'
    ),
    index_dir: Path = typer.Option(
        Path("storage/indexes/default"), "--index", help="Index directory produced by `kiaf index`."
    ),
    top_k: int = typer.Option(5, help="Number of results to check for a hit."),
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Measure retrieval quality (hit-rate@k, MRR) against labeled queries."""
    from know_it_all_friend.embeddings.ollama_embedder import OllamaEmbedder
    from know_it_all_friend.eval.retrieval_eval import evaluate_retrieval, load_eval_cases
    from know_it_all_friend.vectorstore.local_store import LocalVectorStore

    cases = load_eval_cases(cases_file)
    store = LocalVectorStore.load(index_dir)
    embedder = OllamaEmbedder(model=store.embedding_model, host=host)
    report = evaluate_retrieval(cases, store, embedder, top_k=top_k)

    typer.echo(f"\nCases: {report.num_cases}   top_k: {report.top_k}")
    typer.echo(f"Hit-rate@{top_k}: {report.hit_rate:.2%}")
    typer.echo(f"Mean reciprocal rank: {report.mean_reciprocal_rank:.3f}")
    if report.misses:
        typer.echo("\nMissed queries:")
        for query in report.misses:
            typer.echo(f"  - {query}")


@graph_app.command("build")
def graph_build(
    metadata_file: Path = typer.Option(
        Path("storage/metadata/documents.json"), "--metadata", help="Metadata index produced by `kiaf metadata`."
    ),
    entities_file: Path = typer.Option(
        Path("storage/metadata/entities.json"), "--entities", help="Entities produced by `kiaf enrich`."
    ),
    output: Path = typer.Option(
        Path("storage/metadata/graph.json"), "--output", "-o", help="Where to write the graph."
    ),
) -> None:
    """Build the knowledge graph from extracted entities (Phase 12)."""
    from know_it_all_friend.enrichment.extractor import load_entities
    from know_it_all_friend.graph.builder import build_graph, write_graph
    from know_it_all_friend.metadata.extractor import load_metadata

    docs = load_metadata(metadata_file)
    enriched = load_entities(entities_file)
    graph = build_graph(docs, enriched)
    write_graph(graph, output)
    typer.echo(
        f"Graph with {len(graph['documents'])} document(s), {len(graph['entities'])} entit(ies), "
        f"{len(graph['co_occurrences'])} edge(s) written to {output}"
    )


@graph_app.command("related")
def graph_related(
    name: str = typer.Argument(..., help="Entity name to look up (case-insensitive)."),
    graph_file: Path = typer.Option(
        Path("storage/metadata/graph.json"), "--graph", help="Graph produced by `kiaf graph build`."
    ),
    top: int = typer.Option(10, help="How many related entities to show."),
) -> None:
    """Show the documents and entities related to an entity."""
    from know_it_all_friend.graph.builder import load_graph, related_to_entity

    related = related_to_entity(load_graph(graph_file), name)
    if related is None:
        typer.echo(f"Entity not found in the graph: {name!r}")
        raise typer.Exit(code=1)

    typer.echo(f"{related['name']} ({related['type']})\n\nDocuments:")
    for doc in related["documents"]:
        typer.echo(f"  {doc['document_id']}  {doc.get('title', '')} — {doc.get('source_file', '')}")
    if related["related_entities"]:
        typer.echo("\nRelated entities (shared documents):")
        for entity in related["related_entities"][:top]:
            typer.echo(f"  {entity['weight']:3d}  {entity['name']}")


@graph_app.command("doc")
def graph_doc(
    document_id: str = typer.Argument(..., help="Document ID to inspect, e.g. document_001."),
    graph_file: Path = typer.Option(
        Path("storage/metadata/graph.json"), "--graph", help="Graph produced by `kiaf graph build`."
    ),
) -> None:
    """Show the entities mentioned in a document."""
    from know_it_all_friend.graph.builder import load_graph, entities_of_document

    graph = load_graph(graph_file)
    grouped = entities_of_document(graph, document_id)
    if grouped is None:
        typer.echo(f"Document not found in the graph: {document_id!r}")
        raise typer.Exit(code=1)

    info = graph["documents"][document_id]
    typer.echo(f"{document_id}  {info.get('title', '')} — {info.get('source_file', '')}\n")
    for entity_type in sorted(grouped):
        typer.echo(f"{entity_type}: {', '.join(grouped[entity_type])}")


@app.command()
def serve(
    bind: str = typer.Option("127.0.0.1", help="Address to bind the API server to."),
    port: int = typer.Option(8000, help="Port to serve the API on."),
    metadata_file: Path = typer.Option(
        Path("storage/metadata/documents.json"), "--metadata", help="Metadata index produced by `kiaf metadata`."
    ),
    index_dir: Path = typer.Option(
        Path("storage/indexes/default"), "--index", help="Index directory produced by `kiaf index`."
    ),
    model: str = typer.Option("llama3.2", help="Ollama chat model for /ask."),  # keep in sync with rag.ollama_llm.DEFAULT_CHAT_MODEL
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Serve the knowledge base over a REST API (Phase 11)."""
    import uvicorn

    from know_it_all_friend.api.app import create_app

    api = create_app(
        metadata_path=metadata_file,
        index_dir=index_dir,
        ollama_host=host,
        chat_model=model,
    )
    typer.echo(f"Serving API on http://{bind}:{port} (docs at /docs)")
    uvicorn.run(api, host=bind, port=port)


@app.command()
def ui(
    port: int = typer.Option(8501, help="Port to serve the web UI on."),
    metadata_file: Path = typer.Option(
        Path("storage/metadata/documents.json"), "--metadata", help="Metadata index."
    ),
    entities_file: Path = typer.Option(
        Path("storage/metadata/entities.json"), "--entities", help="Entities file."
    ),
    index_dir: Path = typer.Option(
        Path("storage/indexes/default"), "--index", help="Index directory."
    ),
) -> None:
    """Launch the Streamlit knowledge explorer (Phase 11)."""
    import os
    import subprocess
    import sys

    import know_it_all_friend.ui as ui_package

    env = os.environ.copy()
    env["KIAF_METADATA_PATH"] = str(metadata_file)
    env["KIAF_ENTITIES_PATH"] = str(entities_file)
    env["KIAF_INDEX_DIR"] = str(index_dir)

    app_path = Path(ui_package.__file__).parent / "app.py"
    typer.echo(f"Launching knowledge explorer on http://localhost:{port}")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", str(port)],
        check=True,
        env=env,
    )


if __name__ == "__main__":
    app()
