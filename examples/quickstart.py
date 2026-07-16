#!/usr/bin/env python3
"""Quickstart: programmatic usage of Know-it-all Friend.

This script demonstrates how to use the library directly from Python
(without the CLI). It runs the full pipeline on a small collection of
text files and performs a search query.

Prerequisites:
    - Ollama running locally with ``nomic-embed-text`` pulled
    - ``pip install -e .`` (or ``uv pip install -e .``)

Usage:
    python examples/quickstart.py ./my-documents
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(input_dir: str) -> None:
    # --- Step 1: Discover documents -------------------------------------------
    from know_it_all_friend.ingestion.inventory import build_manifest

    records = build_manifest(Path(input_dir))
    print(f"\n📂 Found {len(records)} document(s)")
    for r in records:
        print(f"   {r.filename} ({r.extension}, {r.size_bytes:,} bytes)")

    # --- Step 2: Convert to Markdown ------------------------------------------
    from know_it_all_friend.conversion.markitdown_converter import MarkItDownConverter
    from know_it_all_friend.conversion.pipeline import convert_documents

    output_dir = Path("storage/markdown")
    results = convert_documents(records, MarkItDownConverter(), output_dir)
    ok = sum(1 for r in results if r.status == "success")
    print(f"\n📝 Converted {ok}/{len(results)} document(s) to Markdown")

    # --- Step 3: Extract metadata ---------------------------------------------
    from know_it_all_friend.metadata.extractor import build_document_metadata

    import json

    log_data = [r.__dict__ if hasattr(r, "__dict__") else {} for r in results]
    # Build a minimal conversion log for build_document_metadata
    conversion_log = [
        {
            "document_id": r.document_id,
            "status": r.status,
            "markdown_path": r.markdown_path,
            "timestamp": r.timestamp,
        }
        for r in results
    ]
    docs = build_document_metadata(records, conversion_log)
    print(f"\n📋 Extracted metadata for {len(docs)} document(s)")
    for d in docs:
        print(f"   {d.document_id}: {d.title} ({d.word_count} words)")

    # --- Step 4: Chunk --------------------------------------------------------
    from know_it_all_friend.chunking.chunker import chunk_documents

    chunks = chunk_documents(docs)
    print(f"\n✂️  Created {len(chunks)} chunk(s)")

    # --- Step 5: Embed and index ----------------------------------------------
    from know_it_all_friend.embeddings.ollama_embedder import OllamaEmbedder
    from know_it_all_friend.vectorstore.local_store import build_index

    embedder = OllamaEmbedder()  # uses nomic-embed-text by default
    store = build_index(chunks, embedder)
    index_dir = Path("storage/indexes/default")
    store.save(index_dir)
    print(f"\n🔢 Indexed {len(store)} chunk(s) → {index_dir}")

    # --- Step 6: Search -------------------------------------------------------
    from know_it_all_friend.retrieval.search import search_index

    query = "What are the main topics covered?"
    search_res = search_index(query, store, embedder, top_k=3)
    print(f"\n🔍 Search: '{query}'")
    for i, res in enumerate(search_res, 1):
        print(f"   [{i}] {res.score:.3f}  {res.title} › {res.heading}")
        snippet = " ".join(res.text.split())[:120]
        print(f"       {snippet}...")

    print("\n✅ Pipeline complete! You can now run `kiaf ask` or `kiaf ui` to explore.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python examples/quickstart.py <input-directory>")
        sys.exit(1)
    main(sys.argv[1])
