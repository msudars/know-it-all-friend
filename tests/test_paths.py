"""Tests for storage-root resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from know_it_all_friend.paths import storage_root


def test_kiaf_home_env_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KIAF_HOME", str(tmp_path / "kb"))
    assert storage_root() == tmp_path / "kb"


def test_local_storage_dir_used_when_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KIAF_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "storage").mkdir()
    assert storage_root() == Path("storage")


def test_falls_back_to_home_dot_kiaf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KIAF_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert storage_root() == Path.home() / ".kiaf"
