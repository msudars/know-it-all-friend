from pathlib import Path

import pytest
from watchdog.events import FileModifiedEvent

from know_it_all_friend.watcher import PipelineTriggerHandler


def test_watcher_ignores_its_own_storage_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIAF_HOME", str(tmp_path / "storage"))
    handler = PipelineTriggerHandler(str(tmp_path))

    handler.on_any_event(FileModifiedEvent(str(tmp_path / "storage" / "chunks" / "chunks.json")))
    assert not handler._pending

    handler.on_any_event(FileModifiedEvent(str(tmp_path / "report.pdf")))
    assert handler._pending
