"""Folder watcher to trigger the pipeline automatically (Phase 13)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

class PipelineTriggerHandler(FileSystemEventHandler):
    def __init__(self, input_dir: str, debounce_seconds: float = 3.0):
        self.input_dir = input_dir
        self.debounce_seconds = debounce_seconds
        self._last_event_time = 0.0
        self._pending = False

    def on_any_event(self, event):
        if event.is_directory:
            return
            
        path = str(event.src_path)
        # Skip hidden files or system files we shouldn't trigger on
        if "/." in path or path.startswith("."):
            return
            
        # Only trigger on actual mutations, not reads/opens which happen during ingestion
        if event.event_type not in ("created", "modified", "deleted", "moved"):
            return
            
        logger.info("Change detected: %s (%s)", event.src_path, event.event_type)
        self._last_event_time = time.time()
        self._pending = True

    def check_and_run(self) -> None:
        if not self._pending:
            return
            
        if time.time() - self._last_event_time > self.debounce_seconds:
            self._pending = False
            self._run_pipeline()

    def _run_pipeline(self) -> None:
        logger.info("Changes stabilized. Starting automatic ingestion pipeline...")
        from know_it_all_friend.cli.main import run_ingest

        try:
            run_ingest(Path(self.input_dir))
        except Exception:
            logger.exception("Pipeline failed. Watching for new changes...")
            return

        logger.info("✅ Pipeline completed successfully. Watching for new changes...")


def start_watcher(input_dir: str) -> None:
    """Watch a directory and trigger the pipeline on changes."""
    path = Path(input_dir).resolve()
    if not path.exists():
        logger.error("Directory %s does not exist.", path)
        return

    handler = PipelineTriggerHandler(str(path))
    observer = Observer()
    observer.schedule(handler, str(path), recursive=True)
    observer.start()
    
    logger.info("👀 Watching %s for document changes...", path)
    try:
        while True:
            time.sleep(1.0)
            handler.check_and_run()
    except KeyboardInterrupt:
        logger.info("Stopping watcher...")
        observer.stop()
    observer.join()
