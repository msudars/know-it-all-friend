"""Command-line entry point for Know-it-all Friend (``kiaf``)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from know_it_all_friend.chunking.chunker import DEFAULT_MAX_CHARS, chunk_documents, load_chunks, write_chunks
from know_it_all_friend.conversion.markitdown_converter import MarkItDownConverter
from know_it_all_friend.conversion.pipeline import convert_documents, write_conversion_log
from know_it_all_friend.embeddings.ollama_embedder import DEFAULT_EMBED_MODEL, OllamaEmbedder
from know_it_all_friend.ingestion.inventory import DocumentRecord, build_manifest, write_manifest
from know_it_all_friend.metadata.extractor import build_document_metadata, load_metadata, write_metadata
from know_it_all_friend.rag.answer import answer_question
from know_it_all_friend.rag.ollama_llm import DEFAULT_CHAT_MODEL, OllamaLLM
from know_it_all_friend.retrieval.search import search_index
from know_it_all_friend.vectorstore.local_store import LocalVectorStore, build_index

app = typer.Typer(help="Know-it-all Friend: turn document collections into a knowledge base.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def inventory(
    input_dir: Path = typer.Argument(..., help="Directory of source documents to scan."),
    output: Path = typer.Option(
        Path("storage/metadata/manifest.json"), "--output", "-o", help="Where to write the manifest."
    ),
    recursive: bool = typer.Option(True, help="Recurse into subdirectories."),
) -> None:
    """Scan a directory and write a document manifest (Phase 1)."""
    records = build_manifest(input_dir, recursive=recursive)
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
    records = [DocumentRecord(**r) for r in json.loads(manifest.read_text(encoding="utf-8"))]
    conversion_log = json.loads(log.read_text(encoding="utf-8"))
    docs = build_document_metadata(records, conversion_log)
    write_metadata(docs, output)
    typer.echo(f"Extracted metadata for {len(docs)} document(s). Written to {output}")


@app.command()
def chunk(
    metadata_file: Path = typer.Option(
        Path("storage/metadata/documents.json"), "--metadata", help="Metadata index produced by `kiaf metadata`."
    ),
    output: Path = typer.Option(
        Path("storage/chunks/chunks.json"), "--output", "-o", help="Where to write the chunks."
    ),
    max_chars: int = typer.Option(DEFAULT_MAX_CHARS, help="Maximum characters per chunk."),
) -> None:
    """Split Markdown documents into retrievable chunks (Phase 5)."""
    docs = load_metadata(metadata_file)
    chunks = chunk_documents(docs, max_chars=max_chars)
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
    embed_model: str = typer.Option(DEFAULT_EMBED_MODEL, help="Ollama embedding model to use."),
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Embed chunks with a local Ollama model and build the vector index (Phases 6-7)."""
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
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Semantic search over the indexed chunks (Phase 8)."""
    store = LocalVectorStore.load(index_dir)
    embedder = OllamaEmbedder(model=store.embedding_model, host=host)
    results = search_index(query, store, embedder, top_k=top_k)

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
    model: str = typer.Option(DEFAULT_CHAT_MODEL, help="Ollama chat model to generate the answer."),
    top_k: int = typer.Option(5, help="Number of chunks to retrieve as context."),
    host: str = typer.Option(None, help="Ollama host (defaults to OLLAMA_HOST or localhost)."),
) -> None:
    """Answer a question from retrieved context, with citations (Phase 9)."""
    store = LocalVectorStore.load(index_dir)
    embedder = OllamaEmbedder(model=store.embedding_model, host=host)
    llm = OllamaLLM(model=model, host=host)
    result = answer_question(question, store, embedder, llm, top_k=top_k)

    typer.echo(f"\n{result.answer}\n")
    if result.sources:
        typer.echo("Sources:")
        for number, source in enumerate(result.sources, start=1):
            typer.echo(f"  [{number}] {source.title} — {source.source_file} ({source.chunk_id})")


if __name__ == "__main__":
    app()
