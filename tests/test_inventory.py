import json
from pathlib import Path

import pytest

from know_it_all_friend.ingestion.inventory import build_manifest, discover_files, write_manifest


def test_discover_files_sorted_by_relative_path(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "a.txt").write_text("a")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("c")

    files = discover_files(tmp_path)

    assert [f.relative_to(tmp_path).as_posix() for f in files] == ["a.txt", "b.txt", "sub/c.txt"]


def test_discover_files_non_recursive_skips_subdirectories(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("c")

    files = discover_files(tmp_path, recursive=False)

    assert [f.name for f in files] == ["a.txt"]


def test_discover_files_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        discover_files(tmp_path / "missing")


def test_discover_files_excludes_system_and_sidecar_files(tmp_path: Path) -> None:
    (tmp_path / "report.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "report.pdf:Zone.Identifier").write_text("[ZoneTransfer]")
    (tmp_path / "report.pdf:sec.endpointdlp").write_text("dlp")
    (tmp_path / ".DS_Store").write_bytes(b"\x00")
    (tmp_path / "Thumbs.db").write_bytes(b"\x00")
    (tmp_path / ".hidden_notes").write_text("hidden")

    files = discover_files(tmp_path)

    assert [f.name for f in files] == ["report.pdf"]


def test_discover_files_can_include_system_files(tmp_path: Path) -> None:
    (tmp_path / "report.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "report.pdf:Zone.Identifier").write_text("[ZoneTransfer]")

    files = discover_files(tmp_path, include_system_files=True)

    assert [f.name for f in files] == ["report.pdf", "report.pdf:Zone.Identifier"]


def test_build_manifest_assigns_path_derived_ids(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "b.pdf").write_bytes(b"%PDF-1.4")

    records = build_manifest(tmp_path)

    assert [r.id for r in records] == ["a_txt", "reports_b_pdf"]
    assert records[0].filename == "a.txt"
    assert records[0].extension == "txt"
    assert records[0].size_bytes == 5
    assert records[1].extension == "pdf"


def test_build_manifest_ids_survive_an_inserted_document(tmp_path: Path) -> None:
    """A new file must not renumber the documents that sort after it."""
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "z.txt").write_text("world")
    before = {r.filename: r.id for r in build_manifest(tmp_path)}

    (tmp_path / "m.txt").write_text("inserted")
    after = {r.filename: r.id for r in build_manifest(tmp_path)}

    assert after["a.txt"] == before["a.txt"]
    assert after["z.txt"] == before["z.txt"]


def test_build_manifest_disambiguates_colliding_slugs(tmp_path: Path) -> None:
    (tmp_path / "a-b.txt").write_text("dash")
    (tmp_path / "a_b.txt").write_text("underscore")

    ids = [r.id for r in build_manifest(tmp_path)]

    assert len(set(ids)) == 2
    assert ids[0] == "a_b_txt"
    assert ids[1].startswith("a_b_txt_")


def test_write_manifest_roundtrip(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    records = build_manifest(tmp_path)
    output_path = tmp_path / "manifest.json"

    write_manifest(records, output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data[0]["id"] == "a_txt"
    assert data[0]["filename"] == "a.txt"
