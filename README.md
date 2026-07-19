# Know-it-all Friend 📚

> Turn a folder of documents into a private, searchable knowledge base — semantic search, cited answers, and a knowledge graph, running 100% on your machine.

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Local-first](https://img.shields.io/badge/AI-local--first-orange.svg)](#local-models-via-ollama)

Point it at your PDFs, Word docs, presentations, spreadsheets, and notes. It converts them to Markdown, chunks and embeds them with local models, and gives you search, question answering with citations, and an entity graph — without a single byte leaving your machine.

```text
Documents → Markdown → Chunks → Embeddings → Vector index → Search · Ask · Graph · API · UI
```

---

## Quick Start

**1. Install `kiaf`** (needs [uv](https://docs.astral.sh/uv/)):

```bash
uv tool install git+https://github.com/msudars/know-it-all-friend.git
```

**2. Install [Ollama](https://ollama.com) and pull the two local models:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text   # embeddings (~270 MB)
ollama pull llama3.2           # answers & entity extraction (~2 GB)
```

**3. Build a knowledge base and ask it something:**

```bash
kiaf ingest ~/Documents/my-project
kiaf ask "What information is available about Topic A?"
```

`kiaf ingest` runs the whole pipeline in one go. Pass `--no-enrich` to skip LLM entity extraction and graph building — the slowest steps on large collections.

---

## Commands

| Command | What it does |
| --- | --- |
| `kiaf ingest <dir>` | Build or refresh the knowledge base from a folder, end to end |
| `kiaf search "..."` | Semantic search with sources (`--mode hybrid` fuses in BM25 keyword search, `--diversify` applies MMR) |
| `kiaf ask "..."` | Answer a question from your documents, with numbered citations (`--stream` for live output) |
| `kiaf graph related "Topic A"` | Show documents and co-occurring entities for an entity |
| `kiaf graph doc document_001` | Show the entities mentioned in a document |
| `kiaf watch <dir>` | Watch a folder and re-ingest automatically on changes |
| `kiaf ui` | Launch the Streamlit knowledge explorer (search, ask with evidence, document browser) |
| `kiaf serve` | Serve a REST API (FastAPI, interactive docs at `/docs`) |
| `kiaf eval-retrieval <cases.json>` | Measure retrieval quality (hit-rate@k, MRR) against labeled queries |

Every pipeline stage is also its own command — `inventory`, `convert`, `metadata`, `chunk`, `index`, `enrich`, `graph build` — useful for debugging and inspecting intermediate outputs. Run `kiaf --help` or `kiaf <command> --help` for all options.

---

## Where Data Is Stored

Every command resolves its storage root the same way:

1. `KIAF_HOME` environment variable, if set
2. `./storage`, if it already exists in the current directory
3. `~/.kiaf` otherwise

Point `KIAF_HOME` at different directories to keep separate knowledge bases. All outputs are plain, inspectable files: converted Markdown, JSON metadata and chunks, and a NumPy vector index.

---

## Features

- **One-command ingestion** — discovery, conversion, chunking, embedding, and graph building via `kiaf ingest`, or continuously via `kiaf watch`
- **Broad format support** — PDF, Word, PowerPoint, Excel, Markdown, text, and more via [MarkItDown](https://github.com/microsoft/markitdown)
- **Answers you can check** — every answer cites numbered sources that resolve back to a file, with out-of-range citation detection
- **Serious retrieval** — hybrid BM25 + vector search, MMR diversification, score thresholds, date and document filters, plus an evaluation harness
- **Knowledge graph** — typed entities (people, organizations, projects, technologies, …) and true document dates extracted per document, linked by co-occurrence
- **Deduplication & versioning** — exact-duplicate detection and filename-based version pruning keep stale copies out of the index
- **Inspectable by design** — Markdown as the canonical intermediate format; every stage writes plain files you can read, diff, and version
- **Pluggable** — conversion, embeddings, and LLM backends sit behind small interfaces (`BaseConverter`, `BaseEmbedder`, `BaseLLM`)

---

## Who It's For

The local-first architecture makes it a fit wherever documents can't go to cloud AI:

- **Legal & compliance** — query case files, NDAs, and contracts without uploading client data
- **Investigative journalism** — connect dots across large document troves, securely
- **R&D archives** — cross-reference years of internal reports and lab notes
- **Offline & remote work** — instant answers from manuals in zero-internet environments
- **Personal knowledge management** — notes, papers, and project archives, searchable at last

---

## Local Models via Ollama

Embeddings and answer generation both run through [Ollama](https://ollama.com) on your own machine — document content never leaves it.

- Defaults: `nomic-embed-text` for embeddings, `llama3.2` for chat
- Override with `kiaf ingest --embed-model ... --model ...` (and `kiaf ask --model ...`)
- Ollama running elsewhere? Every model-backed command accepts `--host`

The index records which embedding model built it, so queries always use the matching model.

---

## Development

```bash
git clone https://github.com/msudars/know-it-all-friend.git
cd know-it-all-friend
uv sync              # create .venv and install pinned dependencies
uv run pytest        # run the test suite
uv run kiaf --help
```

See [docs/architecture.md](docs/architecture.md) for how the pipeline stages, interfaces, and storage artifacts fit together. Planned next: server-backed vector stores (e.g. Qdrant) and relationship-aware retrieval.

Contributions welcome — keep examples domain-neutral (Project Alpha, Topic A, Dataset X), prefer inspectable intermediate outputs, and preserve traceability from answer to source document.

---

## License

[MIT](LICENSE) © 2025 Meghana Sudarshan
