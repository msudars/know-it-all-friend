# CLAUDE.md

## Project: Know-it-all Friend

### Overview

Know-it-all Friend framework for transforming heterogeneous document collections into structured, searchable knowledge bases.

The goal is to help individuals and organizations consolidate information distributed across reports, presentations, spreadsheets, publications, meeting notes, web exports, and other document types into a unified knowledge repository.

The project is intentionally domain-agnostic and should be usable across research, industry, education, government, non-profit, and personal knowledge-management contexts.

---

## Core Philosophy

The primary objective is **not** to build a chatbot.

The primary objective is to build robust knowledge infrastructure that enables:

- Document consolidation
- Knowledge discovery
- Search
- Question answering
- Summarization
- Knowledge preservation
- Relationship discovery
- Reusable retrieval workflows

A conversational interface is only one possible way of interacting with the knowledge base.

---

## High-Level Pipeline

```text
Documents
    ↓
Document Inventory
    ↓
Document Conversion
    ↓
Markdown Repository
    ↓
Metadata Extraction
    ↓
Knowledge Enrichment
    ↓
Chunking
    ↓
Embeddings
    ↓
Vector Database
    ↓
Retrieval Engine
    ↓
Search / API / Chat
```

---

## Design Principles

### 1. Markdown First

All supported document types should ultimately be converted into Markdown.

Reasons:

- Human-readable
- Version-control friendly
- LLM-friendly
- Portable
- Easy to inspect and debug
- Suitable for chunking and retrieval pipelines

Markdown is the canonical intermediate format used throughout the pipeline.

---

### 2. Use MarkItDown for the MVP Conversion Layer

For the first implementation, use Microsoft's `markitdown` package as the primary document-to-Markdown converter.

Rationale:

- It provides a simple Python API and CLI.
- It supports common document formats used in knowledge repositories.
- It is designed for converting files into Markdown for LLM and text-analysis workflows.
- It lets the project reach a working MVP quickly.

Initial installation recommendation:

```bash
pip install "markitdown[all]"
```

Basic Python usage:

```python
from markitdown import MarkItDown

converter = MarkItDown(enable_plugins=False)
result = converter.convert("path/to/document.pdf")
markdown_text = result.text_content
```

The project should wrap MarkItDown behind its own converter interface so that other converters can be added later.

Example abstraction:

```python
class BaseConverter:
    def convert(self, path: str) -> str:
        raise NotImplementedError


class MarkItDownConverter(BaseConverter):
    def __init__(self):
        from markitdown import MarkItDown
        self.converter = MarkItDown(enable_plugins=False)

    def convert(self, path: str) -> str:
        result = self.converter.convert(path)
        return result.text_content
```

Do not couple the entire project directly to MarkItDown. Treat it as the first backend, not the permanent architecture.

Future conversion backends may include:

- Docling
- Marker
- Pandoc
- Custom parsers

---

### 3. Domain Agnostic

The framework must never assume a specific field, industry, or internal workflow.

Avoid embedding assumptions related to:

- Scientific disciplines
- Particular companies
- Specific technologies
- Specific project names
- Internal organizational terminology

Use neutral examples such as:

- Project Alpha
- Topic A
- Technology A
- Dataset X
- Document A

The same workflow should work for:

- Research groups
- Universities
- Companies
- Public agencies
- Non-profit organizations
- Individuals

---

### 4. Modular Architecture

Each pipeline stage should operate independently.

Core modules:

```text
ingestion
conversion
metadata
enrichment
chunking
embeddings
vectorstore
retrieval
rag
api
cli
```

Each component should be replaceable without affecting the rest of the system.

---

### 5. Local First

The system should support fully local execution whenever possible.

Benefits:

- Privacy
- Data ownership
- Offline workflows
- Reduced operating costs
- Easier testing and reproducibility

Cloud integrations may be added as optional extensions.

---

### 6. Reproducibility

All outputs should be reproducible.

Given the same inputs and configuration, the system should produce consistent outputs where possible.

Store:

- Configuration files
- Metadata
- Processing logs
- Version information
- Source-to-output mappings

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

## Development Roadmap
Setup uv environment 

### Phase 1 — Document Inventory

Objective:

Create a manifest of available documents.

Input:

```text
input/
```

Output:

```json
[
  {
    "id": "document_001",
    "filename": "document.pdf",
    "extension": "pdf",
    "path": "input/document.pdf",
    "size_bytes": 123456
  }
]
```

Deliverables:

- Directory scanner
- File discovery
- File type detection
- Manifest generation

---

### Phase 2 — Document Conversion

Objective:

Convert supported files into Markdown using MarkItDown as the first conversion backend.

Supported initial types:

```text
PDF
DOCX
PPTX
XLSX
CSV
JSON
XML
HTML
TXT
MD
```

Output location:

```text
storage/markdown/
```

Deliverables:

- `BaseConverter` interface
- `MarkItDownConverter`
- Conversion pipeline
- Markdown output files
- Conversion status logs

---

### Phase 3 — Metadata Extraction

Objective:

Generate structured metadata for every source document and converted Markdown file.

Example:

```json
{
  "document_id": "document_001",
  "title": "Example Report",
  "author": "Jane Doe",
  "date": "2026-01-01",
  "source_file": "input/document.pdf",
  "markdown_file": "storage/markdown/document.md"
}
```

Deliverables:

- Metadata schema
- Metadata storage
- Source-to-Markdown mapping
- Basic automatic metadata extraction

---

### Phase 4 — Knowledge Enrichment

Objective:

Extract useful entities and relationships from document content.

Possible entity types:

```text
People
Organizations
Projects
Products
Datasets
Technologies
Publications
Locations
Topics
```

Deliverables:

- Entity extraction pipeline
- Enriched metadata records
- Optional relationship extraction

---

### Phase 5 — Chunking

Objective:

Split Markdown documents into retrievable units.

Requirements:

- Configurable chunk size
- Configurable overlap
- Metadata preservation
- Section awareness where possible
- Stable chunk IDs

Deliverables:

- Chunking engine
- Chunk metadata store
- Chunk-to-source traceability

---

### Phase 6 — Embeddings

Objective:

Generate vector representations for document chunks.

Potential embedding models:

```text
all-MiniLM
bge-small
bge-large
e5-small
e5-large
```

Deliverables:

- Embedding pipeline
- Embedding configuration
- Embedding storage

---

### Phase 7 — Vector Database

Objective:

Store chunk embeddings and metadata.

Preferred starting option:

```text
Qdrant
```

Alternative options:

```text
ChromaDB
Weaviate
Milvus
```

Deliverables:

- Database integration
- Index creation
- Metadata filtering
- Local development setup

---

### Phase 8 — Retrieval Engine

Objective:

Retrieve relevant information from the knowledge base.

Support:

- Semantic search
- Keyword search
- Hybrid search
- Metadata filters
- Top-k retrieval
- Source traceability

Deliverables:

- Retrieval API
- Search ranking pipeline
- Citation-ready retrieved context

---

### Phase 9 — Search Interface

Objective:

Provide direct search access.

Example:

```bash
kiaf search "example topic"
```

Deliverables:

- CLI commands
- Search output formatting
- Optional JSON output

---

### Phase 10 — RAG Layer

Objective:

Generate answers using retrieved knowledge.

Workflow:

```text
User Question
      ↓
Retrieve Context
      ↓
Build Prompt
      ↓
Generate Response
      ↓
Return Answer with Sources
```

Requirements:

- Citation support
- Source attribution
- Context inspection
- Clear separation between retrieved evidence and generated answer

Deliverables:

- RAG engine
- Citation framework
- Prompt templates

---

### Phase 11 — User Interface

Objective:

Expose functionality through a web application.

Potential features:

- Search interface
- Chat interface
- Document explorer
- Metadata filtering
- Citation viewer
- Processing dashboard

Deliverables:

- Web frontend
- Backend API integration

---

### Phase 12 — Knowledge Graph

Objective:

Build relationships between entities.

Example:

```text
Project Alpha
├── Report
├── Dataset
└── Publication

Technology A
├── Project Alpha
└── Project Beta
```

Deliverables:

- Graph representation
- Graph exploration tools
- Relationship-aware retrieval

---

## Minimum Viable Product (MVP)

The first usable release should include:

- Document inventory
- MarkItDown-based document conversion
- Markdown storage
- Metadata extraction
- Chunking
- Embeddings
- Vector database integration
- Retrieval engine
- Basic RAG interface

Anything beyond this should be considered a future enhancement.

---

## Coding Guidelines

### General

- Keep modules small and focused.
- Avoid premature optimization.
- Prefer readability over cleverness.
- Use type hints where practical.
- Include docstrings for public APIs.
- Keep domain-specific examples out of reusable modules and documentation.

### Logging

Use structured logging where possible.

Important events:

- File discovery
- Conversion success/failure
- Metadata extraction
- Chunk creation
- Embedding creation
- Retrieval operations
- RAG answer generation

### Error Handling

The pipeline should continue processing other files if one file fails.

For each failed file, record:

- Source path
- Error message
- Pipeline stage
- Timestamp

### Testing

Every major component should include:

- Unit tests
- Integration tests
- Small sample datasets
- Tests for unsupported or corrupted files

The repository should maintain a working test suite throughout development.

---

## Future Directions

Potential future capabilities include:

- Multi-user deployments
- Knowledge graph retrieval
- Agent workflows
- Document recommendations
- Automated report generation
- Knowledge gap analysis
- Cross-repository search
- Local and cloud deployment options
- Plugin ecosystem
- Advanced document layout understanding
- Human-in-the-loop metadata correction

---

## Success Criteria

Know-it-all Friend succeeds if a user can:

1. Drop documents into a folder.
2. Build a knowledge base from those documents.
3. Inspect the generated Markdown.
4. Search the collected knowledge.
5. Ask questions with citations.
6. Discover relationships between information sources.
7. Preserve and reuse organizational knowledge over time.

The project should prioritize robustness, transparency, modularity, and reproducibility over flashy user interfaces or complex agent behavior.
