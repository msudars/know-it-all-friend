# Know-it-all Friend

> Convert folders of documents into a structured, searchable knowledge base for search, discovery, and retrieval-augmented generation.

Know-it-all Friend is an open-source, domain-agnostic framework for consolidating information from documents such as reports, presentations, spreadsheets, publications, meeting notes, web exports, and text files.

The project helps users move from managing scattered files to managing reusable knowledge.

---

## What This Project Does

Know-it-all Friend takes a folder of documents and turns it into a knowledge base.

```text
Documents
    ↓
Markdown
    ↓
Metadata
    ↓
Chunks
    ↓
Embeddings
    ↓
Vector Database
    ↓
Search / API / Chat
```

The first implementation uses Microsoft's `markitdown` package as the primary document-to-Markdown conversion backend.

See [docs/architecture.md](docs/architecture.md) for how the pipeline stages, interfaces, and storage artifacts fit together.

---

## Why Markdown?

Markdown is used as the canonical intermediate format because it is:

- Human-readable
- Easy to version control
- Easy to inspect and debug
- Friendly to LLM and retrieval workflows
- Suitable for chunking and metadata extraction

Rather than sending raw PDFs, presentations, spreadsheets, and office documents directly into a RAG system, Know-it-all Friend first converts them into a cleaner Markdown representation.

---

## Key Features

Available today:

- Recursive document discovery (with OS/sidecar junk-file exclusion)
- Document conversion to Markdown
- Metadata extraction
- Markdown repository creation
- LLM-based entity and topic extraction
- Heading-aware document chunking with word-boundary-safe overlap between consecutive chunks
- Embedding generation (local, via Ollama)
- On-disk vector index
- Semantic search, with optional BM25 hybrid keyword search, MMR result diversification, score thresholds, and document-ID filtering
- Retrieval-augmented question answering with source citations, out-of-range citation detection, and streaming answers
- Retrieval quality evaluation harness (hit-rate@k, MRR) against labeled queries
- Content-hash based document staleness detection
- Knowledge graph over documents and entities
- REST API
- Web knowledge explorer (search, ask with evidence, document browser)

Planned:

- Server-backed vector stores (e.g. Qdrant)
- Relationship-aware retrieval

---

## Domain-Agnostic by Design

Know-it-all Friend is not designed for one specific field or organization.

It can be used for:

- Research documentation
- Technical documentation
- Internal knowledge repositories
- Policy and compliance documents
- Educational materials
- Meeting notes
- Project archives
- Digital libraries
- Personal knowledge management

Examples in this repository should use neutral placeholders such as:

- Project Alpha
- Topic A
- Technology A
- Dataset X
- Document A

Avoid adding proprietary, organization-specific, or domain-specific terminology to public examples.

---

## Installation

Know-it-all Friend uses [uv](https://docs.astral.sh/uv/) for environment and dependency management.

### 1. Clone the repository

```bash
git clone https://github.com/msudars/know-it-all-friend.git
cd know-it-all-friend
```

### 2. Install uv (if you don't already have it)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Create the environment and install dependencies

```bash
uv sync
```

This creates a project-local `.venv/` and installs the package plus its dependencies — including MarkItDown's `pdf`, `docx`, `pptx`, and `xlsx` extras — at the exact versions pinned in `uv.lock`, so every clone of this repo resolves to the same environment.

### 4. Run the CLI

```bash
uv run kiaf --help
```

`uv run` executes commands inside the project's `.venv` without needing to activate it manually. If you prefer an activated shell:

```bash
source .venv/bin/activate
kiaf --help
```

---

## Repository Structure

```text
know-it-all-friend/
├── docs/                     # architecture and design notes
├── tests/
├── storage/                  # pipeline outputs (gitignored, regenerable)
│   ├── markdown/             # converted documents
│   ├── chunks/               # chunked retrieval units
│   ├── metadata/             # manifest, conversion log, metadata, entities, graph
│   └── indexes/              # vector indexes
│
├── know_it_all_friend/
│   ├── ingestion/            # Phase 1  — discovery + manifest
│   ├── conversion/           # Phase 2  — MarkItDown → Markdown
│   ├── metadata/             # Phase 3  — per-document metadata
│   ├── enrichment/           # Phase 4  — LLM entity/topic extraction
│   ├── chunking/             # Phase 5  — heading-aware chunking
│   ├── embeddings/           # Phase 6  — BaseEmbedder + Ollama backend
│   ├── vectorstore/          # Phase 7  — local on-disk vector index
│   ├── retrieval/            # Phase 8  — semantic search
│   ├── rag/                  # Phase 9  — cited answers, BaseLLM + Ollama backend
│   ├── graph/                # Phase 12 — knowledge graph
│   ├── api/                  # Phase 11 — FastAPI REST layer
│   ├── ui/                   # Phase 11 — Streamlit knowledge explorer
│   └── cli/                  # the `kiaf` command
│
├── pyproject.toml
├── uv.lock
├── README.md
├── claude.md
├── LICENSE
└── .gitignore
```

---

## Quick Start: MVP Workflow

### Step 1: Add documents

Place files into an input directory:

```text
input/
├── report.docx
├── presentation.pptx
├── publication.pdf
├── table.xlsx
└── notes.md
```

### Step 2: Create a document inventory

Available now:

```bash
uv run kiaf inventory input/ --output storage/metadata/manifest.json
```

Output (`storage/metadata/manifest.json`):

```json
[
  {
    "id": "document_001",
    "filename": "report.docx",
    "extension": "docx",
    "path": "input/report.docx",
    "size_bytes": 123456
  }
]
```

Files are discovered recursively by default (pass `--no-recursive` to scan only the top level) and IDs are assigned in sorted path order, so the manifest is reproducible across runs on the same input set. Hidden dotfiles, OS bookkeeping files (`.DS_Store`, `Thumbs.db`), and NTFS sidecar streams (`report.pdf:Zone.Identifier`) are skipped; pass `--include-system-files` to inventory them anyway.

### Step 3: Convert documents to Markdown

Available now:

```bash
uv run kiaf convert --manifest storage/metadata/manifest.json --output storage/markdown/
```

Output:

```text
storage/markdown/
├── document_001.md
├── document_002.md
├── document_003.md
└── document_004.md
```

Markdown files are named by document ID rather than original filename, since two source files can share a name across different input subfolders — the ID is the stable join key back to the manifest. A per-file status log is written to `storage/metadata/conversion_log.json`; a failure on one document (unsupported format, corrupt file) is recorded there and does not stop the rest of the batch from converting.

### Step 4: Extract metadata

Available now:

```bash
uv run kiaf metadata
```

Joins the manifest with the conversion log and the converted Markdown to produce `storage/metadata/documents.json`:

```json
{
  "document_id": "document_001",
  "title": "Example Report",
  "source_file": "input/report.docx",
  "markdown_file": "storage/markdown/document_001.md",
  "extension": "docx",
  "size_bytes": 123456,
  "word_count": 842
}
```

The title comes from the first Markdown heading, falling back to the filename. Documents whose conversion failed are skipped (they have no Markdown to work with) without blocking the rest.

### Step 5: Chunk documents

Available now:

```bash
uv run kiaf chunk
```

Splits each Markdown document at its headings, then packs long sections paragraph-by-paragraph so no chunk exceeds `--max-chars` (default 1500). Chunks carry their document ID, title, source path, and nearest heading, and are written to `storage/chunks/chunks.json`.

### Step 6: Build embeddings and vector index

Available now (requires a running [Ollama](https://ollama.com) server, see below):

```bash
uv run kiaf index
```

Embeds every chunk with a local Ollama embedding model (default `nomic-embed-text`) and writes a local vector index to `storage/indexes/default/` — three plain, inspectable files: `embeddings.npy`, `chunks.json`, and `config.json`. The config records which embedding model built the index so queries always use the same one.

### Step 7: Search

Available now:

```bash
uv run kiaf search "Topic A"
```

Embeds the query, ranks chunks by cosine similarity, and prints the top matches with document titles, source paths, and snippets.

### Step 8: Ask questions with retrieved context

Available now:

```bash
uv run kiaf ask "What information is available about Topic A?"
```

Retrieves the most relevant chunks, sends them as numbered sources to a local Ollama chat model (default `llama3.2`, override with `--model`), and prints the answer followed by the numbered source list so every citation resolves back to a file.

### Step 9: Extract entities and build the knowledge graph

Available now:

```bash
uv run kiaf enrich
uv run kiaf graph build
uv run kiaf graph related "Topic A"
uv run kiaf graph doc document_001
```

`kiaf enrich` extracts typed entities (people, organizations, projects, products, datasets, technologies, publications, locations, topics) from each document with the local chat model, writing `storage/metadata/entities.json`. `kiaf graph build` turns those into `storage/metadata/graph.json` — document→entity mentions plus entity↔entity co-occurrence edges weighted by shared documents — which `kiaf graph related` and `kiaf graph doc` explore from the command line.

### Step 10: Serve the REST API

Available now:

```bash
uv run kiaf serve
```

Exposes the knowledge base as JSON on `http://127.0.0.1:8000` (interactive docs at `/docs`): `GET /documents`, `GET /search?q=...`, `POST /ask`, `GET /health`. Backends are pluggable, so other frontends can build on this without touching the pipeline.

### Step 11: Explore in the web UI

Available now:

```bash
uv run kiaf ui
```

Launches a local Streamlit knowledge explorer on `http://localhost:8501` with three views: semantic **Search**, **Ask** (the generated answer side-by-side with the retrieved evidence it came from), and a **Documents** table with extracted entities and converted-Markdown previews. The UI is search-first by design — chat is one panel, not the front door.

---

## Local Models via Ollama

The MVP is local-first: embeddings and answer generation both run through [Ollama](https://ollama.com) on your own machine, so document content never leaves it. One-time setup:

```bash
curl -fsSL https://ollama.com/install.sh | sh   # or your platform's installer
ollama pull nomic-embed-text                    # embedding model (~270 MB)
ollama pull llama3.2                            # chat model (~2 GB)
```

All model-backed commands accept `--host` if Ollama runs somewhere other than `localhost:11434`, and `kiaf index --embed-model` / `kiaf ask --model` to use different models.

Like conversion, the model backends sit behind interfaces (`BaseEmbedder`, `BaseLLM`) so hosted APIs or other local runtimes can be added later without touching the pipeline.

---

## MarkItDown Conversion Backend

The MVP uses MarkItDown for converting files to Markdown, wrapped behind an internal interface so the rest of the pipeline never depends on MarkItDown directly:

- [`know_it_all_friend/conversion/base.py`](know_it_all_friend/conversion/base.py) — the `BaseConverter` interface
- [`know_it_all_friend/conversion/markitdown_converter.py`](know_it_all_friend/conversion/markitdown_converter.py) — `MarkItDownConverter`, the first backend
- [`know_it_all_friend/conversion/pipeline.py`](know_it_all_friend/conversion/pipeline.py) — runs a converter over a manifest, writing Markdown files and a per-file status log

This keeps the architecture flexible so future conversion backends can be added without rewriting the whole pipeline.

Potential future backends:

- Docling
- Marker
- Pandoc
- Custom parsers

---

## MVP Scope

The first usable version should include:

- File discovery
- Manifest creation
- MarkItDown-based conversion
- Markdown storage
- Metadata extraction
- Chunking
- Embedding generation
- Vector database integration
- Semantic search
- Basic RAG question answering with citations

Do not start with a complex chatbot interface. Build the knowledge layer first.

---

## Development Roadmap

All roadmap phases have shipped; remaining work is post-roadmap (see Project Status).

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Document inventory (`kiaf inventory`) | ✅ |
| 2 | Conversion to Markdown via MarkItDown (`kiaf convert`) | ✅ |
| 3 | Metadata extraction (`kiaf metadata`) | ✅ |
| 4 | Knowledge enrichment — entities and topics (`kiaf enrich`) | ✅ |
| 5 | Heading-aware chunking (`kiaf chunk`) | ✅ |
| 6 | Embeddings via local Ollama models (`kiaf index`) | ✅ |
| 7 | Vector storage — local on-disk index (`kiaf index`) | ✅ (server-backed stores planned, see #5) |
| 8 | Retrieval — semantic search, hybrid BM25 + MMR + filters (`kiaf search`) | ✅ |
| 9 | RAG with citations (`kiaf ask`) | ✅ |
| 10 | UI and knowledge graph (`kiaf ui`, `kiaf serve`, `kiaf graph`) | ✅ |

---

## Development Principles

- Keep the system modular.
- Keep the public examples domain-neutral.
- Prefer inspectable intermediate outputs.
- Save Markdown, metadata, and logs.
- Preserve traceability from answer to source document.
- Prioritize robustness over flashy demos.
- Support local-first workflows where possible.

---

## Example Use Cases

### Search across project archives

```text
Find documents related to Topic A.
```

### Summarize a collection

```text
Summarize all documents associated with Project Alpha.
```

### Retrieve supporting evidence

```text
Which documents mention Dataset X?
```

### Ask questions with citations

```text
What information is available about Technology A?
```

---

## License

[MIT](LICENSE) © 2025 Meghana Sudarshan

---

## Project Status

**MVP complete.** The full pipeline works end-to-end, with tests:

- `kiaf inventory` — document discovery and manifest
- `kiaf convert` — MarkItDown-based conversion to Markdown
- `kiaf metadata` — per-document metadata extraction
- `kiaf chunk` — heading-aware Markdown chunking with word-boundary-safe overlap
- `kiaf index` — local embeddings (Ollama) + on-disk vector index
- `kiaf search` — semantic search with sources; optional hybrid BM25, MMR diversification, score threshold, document filtering
- `kiaf ask` — RAG question answering with citations, streaming, and out-of-range citation warnings, via a local Ollama chat model
- `kiaf eval-retrieval` — retrieval quality evaluation (hit-rate@k, MRR) against labeled queries
- `kiaf enrich` — LLM-based entity and topic extraction
- `kiaf graph` — knowledge graph over documents and entities (`build` / `related` / `doc`)
- `kiaf serve` — REST API (FastAPI) over the knowledge base
- `kiaf ui` — Streamlit knowledge explorer (search, ask with evidence, document browser)

Not yet built (post-MVP roadmap): server-backed vector stores (e.g. Qdrant), relationship-aware retrieval, and multi-user deployments.
