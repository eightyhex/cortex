"""File watcher — watchdog-based file system watcher for vault changes."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from cortex.vault.parser import parse_note

if TYPE_CHECKING:
    from cortex.graph.manager import GraphManager
    from cortex.index.manager import IndexManager

logger = logging.getLogger(__name__)

# Patterns to ignore
_IGNORE_SUFFIXES = {".md~", ".tmp", ".swp", ".swo"}
_IGNORE_DIRS = {".obsidian", ".trash", "_templates"}

DEBOUNCE_SECONDS = 0.5


class _VaultEventHandler(FileSystemEventHandler):
    """Handles file system events with debouncing."""

    def __init__(
        self,
        vault_path: Path,
        index_manager: IndexManager,
        graph_manager: GraphManager,
    ) -> None:
        super().__init__()
        self._vault_path = vault_path
        self._index = index_manager
        self._graph = graph_manager
        self._pending: dict[str, tuple[str, float]] = {}  # path -> (event_type, timestamp)
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _should_ignore(self, path: str) -> bool:
        """Check if the event path should be ignored."""
        p = Path(path)
        # Only care about .md files
        if p.suffix != ".md":
            return True
        # Ignore temp file suffixes
        if any(path.endswith(s) for s in _IGNORE_SUFFIXES):
            return True
        # Ignore paths inside ignored directories
        try:
            rel = p.relative_to(self._vault_path)
        except ValueError:
            return True
        for part in rel.parts:
            if part in _IGNORE_DIRS:
                return True
        return False

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._schedule(event.src_path, "create")

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._schedule(event.src_path, "modify")

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._schedule(event.src_path, "delete")

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            # Treat as delete old + create new
            if not self._should_ignore(event.src_path):
                self._schedule(event.src_path, "delete")
            if hasattr(event, "dest_path") and not self._should_ignore(event.dest_path):
                self._schedule(event.dest_path, "create")

    def _schedule(self, path: str, event_type: str) -> None:
        """Schedule a debounced processing of the event."""
        with self._lock:
            self._pending[path] = (event_type, time.monotonic())
            # Reset debounce timer
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SECONDS, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        """Process all pending events."""
        with self._lock:
            events = dict(self._pending)
            self._pending.clear()

        for path_str, (event_type, _ts) in events.items():
            path = Path(path_str)
            try:
                if event_type == "delete":
                    self._handle_delete(path)
                else:
                    self._handle_upsert(path)
            except Exception:
                logger.exception("Error processing %s event for %s", event_type, path)

    def _handle_upsert(self, path: Path) -> None:
        """Handle a created or modified file."""
        if not path.exists():
            return
        note = parse_note(path)
        self._index.reindex_note(note)
        self._graph.update_note(note)
        logger.info("Reindexed: %s", path.name)

    def _handle_delete(self, path: Path) -> None:
        """Handle a deleted file — need to find the note_id from the path."""
        # We need the note_id but the file is gone. Try to find it from the
        # index by scanning for a note whose path matches.
        note_id = self._find_note_id_by_path(path)
        if note_id:
            self._index.remove_note(note_id)
            self._graph.remove_note(note_id)
            logger.info("Removed from index: %s (id=%s)", path.name, note_id)
        else:
            logger.warning("Could not find note_id for deleted file: %s", path)

    def _find_note_id_by_path(self, path: Path) -> str | None:
        """Look up a note_id by file path from the graph nodes."""
        path_str = str(path)
        for node_id, data in self._graph._graph.nodes(data=True):
            if data.get("path") == path_str:
                return node_id
        return None


class VaultWatcher:
    """Watches vault directory for file changes and triggers index updates."""

    def __init__(
        self,
        vault_path: Path,
        index_manager: IndexManager,
        graph_manager: GraphManager,
    ) -> None:
        self._vault_path = vault_path
        self._handler = _VaultEventHandler(vault_path, index_manager, graph_manager)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(vault_path), recursive=True)

    def start(self) -> None:
        """Start watching for file changes."""
        self._observer.start()
        logger.info("Watching vault at %s", self._vault_path)

    def stop(self) -> None:
        """Stop watching for file changes."""
        self._observer.stop()
        self._observer.join(timeout=5)
        logger.info("Stopped watching vault")

    @property
    def handler(self) -> _VaultEventHandler:
        """Expose the handler for testing."""
        return self._handler
