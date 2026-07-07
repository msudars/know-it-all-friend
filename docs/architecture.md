# Architecture

Know-it-all Friend is a pipeline of independent stages. Each stage reads the
previous stage's output from `storage/`, writes its own inspectable artifact
there, and can be re-run or replaced without touching the rest of the system.

## Pipeline stages

| Stage | Command | Module | Reads | Writes |
| --- | --- | --- | --- | --- |
| Inventory | `kiaf inventory <dir>` | `ingestion/inventory.py` | input directory | `storage/metadata/manifest.json` |
| Conversion | `kiaf convert` | `conversion/pipeline.py` | manifest + source files | `storage/markdown/<id>.md`, `storage/metadata/conversion_log.json` |
| Metadata | `kiaf metadata` | `metadata/extractor.py` | manifest + conversion log + Markdown | `storage/metadata/documents.json` |
| Enrichment | `kiaf enrich` | `enrichment/extractor.py` | metadata + Markdown (via local LLM) | `storage/metadata/entities.json` |
| Chunking | `kiaf chunk` | `chunking/chunker.py` | metadata + Markdown | `storage/chunks/chunks.json` |
| Indexing | `kiaf index` | `vectorstore/local_store.py` | chunks (via embedder) | `storage/indexes/default/` |
| Search | `kiaf search` | `retrieval/search.py` | index (via embedder) | — |
| RAG | `kiaf ask` | `rag/answer.py` | index (via embedder + LLM) | — |
| Graph | `kiaf graph build` | `graph/builder.py` | metadata + entities | `storage/metadata/graph.json` |

The document ID (`document_001`, …) assigned at inventory time is the join key
across every artifact; chunk IDs (`document_001_chunk_0000`) extend it, so any
search hit or citation traces back to the exact source file.

## Interfaces and backends

External engines sit behind small interfaces so backends can be swapped
without touching the pipeline:

| Interface | Module | First backend |
| --- | --- | --- |
| `BaseConverter` | `conversion/base.py` | MarkItDown (`markitdown_converter.py`) |
| `BaseEmbedder` | `embeddings/base.py` | Ollama, default `nomic-embed-text` (`ollama_embedder.py`) |
| `BaseLLM` | `rag/base.py` | Ollama, default `llama3.2` (`ollama_llm.py`) |

Everything model-backed runs through a local Ollama server by default —
document content never leaves the machine. All model-backed commands accept
`--host` for a non-local Ollama.

## Vector index layout

`storage/indexes/default/` is three plain files, deliberately inspectable:

- `embeddings.npy` — one float32 row per chunk
- `chunks.json` — the chunk records, row-aligned with the embeddings
- `config.json` — which embedding model built the index (queries always
  re-use it)

Search is cosine similarity over the full matrix; fine for personal-scale
collections, and the seam where a server-backed store (e.g. Qdrant, issue #5)
would plug in.

## Frontends

Both frontends consume the same service layer (`retrieval/search.py`,
`rag/answer.py`) rather than each other:

- **REST API** (`kiaf serve`, `api/app.py`) — `GET /documents`, `GET /search`,
  `POST /ask`, `GET /health`; backends are constructor-injectable, and missing
  pipeline outputs return `503` with guidance instead of crashing.
- **Web UI** (`kiaf ui`, `ui/app.py`) — Streamlit knowledge explorer,
  search-first by design: Search, Ask (answer rendered beside the retrieved
  evidence), and a Documents browser with extracted entities.

## Error-handling and testing conventions

- **Skip-and-continue:** a bad file (corrupt, unreadable, failed model call)
  is logged and skipped at every stage; one document never blocks the batch.
- **Determinism:** discovery order, document/chunk IDs, and index layout are
  stable across runs on the same input.
- **Tests without models:** every model-touching module is tested through its
  interface with deterministic fakes (`tests/test_*.py`), so the suite runs
  without an Ollama server. `streamlit.testing.v1.AppTest` executes the UI
  script; FastAPI's `TestClient` covers the API.
