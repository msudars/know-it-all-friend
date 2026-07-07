"""Command-line entry point for Know-it-all Friend (``kiaf``)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from know_it_all_friend.conversion.markitdown_converter import MarkItDownConverter
from know_it_all_friend.conversion.pipeline import (
    ConversionResult,
    convert_documents,
    write_conversion_log,
)
from know_it_all_friend.ingestion.inventory import DocumentRecord, build_manifest, write_manifest
from know_it_all_friend.metadata.extractor import build_metadata, write_metadata_index

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
    conversion_log: Path = typer.Option(
        Path("storage/metadata/conversion_log.json"), "--conversion-log", help="Log produced by `kiaf convert`."
    ),
    output: Path = typer.Option(
        Path("storage/metadata/metadata.json"), "--output", "-o", help="Where to write the metadata index."
    ),
) -> None:
    """Extract structured metadata for every document (Phase 3)."""
    records = [DocumentRecord(**r) for r in json.loads(manifest.read_text(encoding="utf-8"))]
    results = [ConversionResult(**r) for r in json.loads(conversion_log.read_text(encoding="utf-8"))]
    entries = build_metadata(records, results)
    write_metadata_index(entries, output)

    with_markdown = sum(1 for e in entries if e.markdown_file is not None)
    typer.echo(
        f"Extracted metadata for {len(entries)} document(s) "
        f"({with_markdown} with Markdown). Index written to {output}"
    )


if __name__ == "__main__":
    app()
