"""Integration tests for the CLI entry point.

These exercise commands that work purely on local files (no Ollama server
required). Commands that need a running Ollama instance are covered by
the unit tests for their underlying modules.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from know_it_all_friend.cli.main import app

runner = CliRunner()


def _create_sample_file(directory: Path, name: str = "sample.txt", content: str = "Hello world") -> Path:
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


def test_inventory_discovers_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _create_sample_file(input_dir, "doc1.txt")
    _create_sample_file(input_dir, "doc2.pdf", content="fake pdf")
    manifest_path = tmp_path / "manifest.json"

    result = runner.invoke(app, ["inventory", str(input_dir), "--output", str(manifest_path)])

    assert result.exit_code == 0, result.output
    assert "2 document(s)" in result.output
    assert manifest_path.exists()
    records = json.loads(manifest_path.read_text())
    assert len(records) == 2


def test_inventory_empty_directory(tmp_path: Path) -> None:
    input_dir = tmp_path / "empty"
    input_dir.mkdir()
    manifest_path = tmp_path / "manifest.json"

    result = runner.invoke(app, ["inventory", str(input_dir), "--output", str(manifest_path)])

    assert result.exit_code == 0, result.output
    assert "0 document(s)" in result.output


def test_inventory_skips_hidden_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _create_sample_file(input_dir, "visible.txt")
    _create_sample_file(input_dir, ".hidden")
    manifest_path = tmp_path / "manifest.json"

    result = runner.invoke(app, ["inventory", str(input_dir), "--output", str(manifest_path)])

    assert result.exit_code == 0, result.output
    assert "1 document(s)" in result.output


def test_metadata_from_converted_markdown(tmp_path: Path) -> None:
    """inventory -> fake conversion log -> metadata pipeline."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _create_sample_file(input_dir, "report.txt", content="# My Report\n\nSome content here.")

    manifest_path = tmp_path / "manifest.json"
    result = runner.invoke(app, ["inventory", str(input_dir), "--output", str(manifest_path)])
    assert result.exit_code == 0, result.output

    records = json.loads(manifest_path.read_text())
    doc_id = records[0]["id"]

    # Create a fake conversion log and markdown output
    md_dir = tmp_path / "markdown"
    md_dir.mkdir()
    md_path = md_dir / f"{doc_id}.md"
    md_path.write_text("# My Report\n\nSome content here.", encoding="utf-8")

    log_path = tmp_path / "conversion_log.json"
    log_data = [
        {
            "document_id": doc_id,
            "status": "success",
            "markdown_path": str(md_path),
            "timestamp": "2025-01-01T00:00:00+00:00",
        }
    ]
    log_path.write_text(json.dumps(log_data), encoding="utf-8")

    metadata_path = tmp_path / "documents.json"
    result = runner.invoke(
        app,
        ["metadata", "--manifest", str(manifest_path), "--log", str(log_path), "--output", str(metadata_path)],
    )

    assert result.exit_code == 0, result.output
    assert "1 document(s)" in result.output
    docs = json.loads(metadata_path.read_text())
    assert docs[0]["title"] == "My Report"


def test_chunk_splits_markdown(tmp_path: Path) -> None:
    """Chunking from metadata produces chunks."""
    md_dir = tmp_path / "markdown"
    md_dir.mkdir()
    md_path = md_dir / "document_001.md"
    md_path.write_text("# Chapter 1\n\nParagraph one.\n\n# Chapter 2\n\nParagraph two.", encoding="utf-8")

    metadata_path = tmp_path / "documents.json"
    metadata_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "document_001",
                    "title": "Test Doc",
                    "source_file": "input/test.txt",
                    "markdown_file": str(md_path),
                    "extension": "txt",
                    "size_bytes": 100,
                    "word_count": 8,
                    "content_hash": "",
                    "modified_at": "",
                }
            ]
        ),
        encoding="utf-8",
    )

    chunks_path = tmp_path / "chunks.json"
    result = runner.invoke(
        app, ["chunk", "--metadata", str(metadata_path), "--output", str(chunks_path)]
    )

    assert result.exit_code == 0, result.output
    assert "chunk(s)" in result.output
    chunks = json.loads(chunks_path.read_text())
    assert len(chunks) >= 1


def test_help_is_fast() -> None:
    """--help should work without errors (validates lazy imports don't break)."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Know-it-all Friend" in result.output


def test_subcommand_help_works() -> None:
    for cmd in ["inventory", "convert", "metadata", "enrich", "chunk", "index", "search", "ask", "serve"]:
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0, f"{cmd} --help failed: {result.output}"


def test_graph_subcommand_help_works() -> None:
    for cmd in ["build", "related", "doc"]:
        result = runner.invoke(app, ["graph", cmd, "--help"])
        assert result.exit_code == 0, f"graph {cmd} --help failed: {result.output}"
