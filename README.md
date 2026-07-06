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

Planned and/or in-progress features:

- Recursive document discovery
- Document conversion to Markdown
- Metadata extraction
- Markdown repository creation
- Document chunking
- Embedding generation
- Vector database storage
- Semantic search
- Metadata filtering
- Retrieval-augmented question answering
- Source citations
- Optional web interface
- Optional knowledge graph

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

### 1. Clone the repository

```bash
git clone https://github.com/<your-org-or-username>/know-it-all-friend.git
cd know-it-all-friend
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

For the MVP conversion layer:

```bash
pip install "markitdown[all]"
```

When the project package is available locally:

```bash
pip install -e .
```

---

## Recommended Repository Structure

```text
know-it-all-friend/
├── docs/
├── examples/
├── tests/
├── storage/
│   ├── markdown/
│   ├── chunks/
│   ├── metadata/
│   └── indexes/
│
├── know_it_all_friend/
│   ├── __init__.py
│   ├── ingestion/
│   ├── conversion/
│   ├── metadata/
│   ├── enrichment/
│   ├── chunking/
│   ├── embeddings/
│   ├── vectorstore/
│   ├── retrieval/
│   ├── rag/
│   ├── api/
│   └── cli/
│
├── pyproject.toml
├── README.md
├── CLAUDE.md
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

Planned command:

```bash
kiaf inventory input/ --output storage/manifest.json
```

Expected output:

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

### Step 3: Convert documents to Markdown

Planned command:

```bash
kiaf convert input/ --output storage/markdown/
```

Expected output:

```text
storage/markdown/
├── report.md
├── presentation.md
├── publication.md
├── table.md
└── notes.md
```

### Step 4: Extract metadata

Planned command:

```bash
kiaf metadata storage/markdown/ --output storage/metadata/
```

Example metadata:

```json
{
  "document_id": "document_001",
  "title": "Example Report",
  "source_file": "input/report.docx",
  "markdown_file": "storage/markdown/report.md",
  "topics": ["Topic A", "Topic B"]
}
```

### Step 5: Chunk documents

Planned command:

```bash
kiaf chunk storage/markdown/ --output storage/chunks/
```

### Step 6: Build embeddings and vector index

Planned command:

```bash
kiaf index storage/chunks/ --vectorstore qdrant
```

### Step 7: Search

Planned command:

```bash
kiaf search "Topic A"
```

### Step 8: Ask questions with retrieved context

Planned command:

```bash
kiaf ask "What information is available about Topic A?"
```

---

## MarkItDown Conversion Backend

The MVP uses MarkItDown for converting files to Markdown.

Example Python usage:

```python
from markitdown import MarkItDown

converter = MarkItDown(enable_plugins=False)
result = converter.convert("input/report.docx")
markdown_text = result.text_content

with open("storage/markdown/report.md", "w", encoding="utf-8") as f:
    f.write(markdown_text)
```

Know-it-all Friend should wrap MarkItDown behind an internal interface:

```python
class BaseConverter:
    def convert(self, path: str) -> str:
        raise NotImplementedError
```

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

### Phase 1: Document Inventory

Create a manifest of all files in the input directory.

### Phase 2: Document Conversion

Convert files to Markdown using MarkItDown.

### Phase 3: Metadata Extraction

Extract basic metadata from files and Markdown content.

### Phase 4: Knowledge Enrichment

Extract topics, entities, and relationships.

### Phase 5: Chunking

Split Markdown documents into retrievable units.

### Phase 6: Embeddings

Generate vector representations of chunks.

### Phase 7: Vector Database

Store chunks, embeddings, and metadata.

### Phase 8: Retrieval

Support semantic search, keyword search, and metadata filters.

### Phase 9: RAG

Generate answers using retrieved context and provide citations.

### Phase 10: UI and Knowledge Graph

Add a web interface and relationship-aware exploration.

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

Add your chosen license here.

Recommended for open-source projects:

- MIT
- Apache-2.0
- BSD-3-Clause

---

## Project Status

Early planning / MVP implementation.

The first priority is the document-to-Markdown pipeline, followed by metadata, chunking, retrieval, and RAG.
