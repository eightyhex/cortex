"""Tests for VaultWatcher — file system event handling with debouncing."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.vault.watcher import VaultWatcher, _VaultEventHandler


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    """Create a vault directory with a note."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "00-inbox").mkdir()
    return vault


@pytest.fixture
def mock_index():
    return MagicMock()


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    graph._graph = MagicMock()
    graph._graph.nodes = MagicMock(return_value=[])
    return graph


@pytest.fixture
def handler(vault_dir: Path, mock_index, mock_graph) -> _VaultEventHandler:
    return _VaultEventHandler(vault_dir, mock_index, mock_graph)


def _make_note(vault_dir: Path, folder: str, filename: str, content: str) -> Path:
    """Create a note file and return its path."""
    folder_path = vault_dir / folder
    folder_path.mkdir(exist_ok=True)
    note_path = folder_path / filename
    note_path.write_text(content, encoding="utf-8")
    return note_path


def _wait_for_debounce():
    """Wait for the debounce timer to fire."""
    time.sleep(0.8)


class TestCreateEvent:
    def test_create_triggers_reindex(self, vault_dir, mock_index, mock_graph, handler):
        """Creating a .md file triggers reindex_note and update_note."""
        note_path = _make_note(
            vault_dir,
            "00-inbox",
            "test-note.md",
            "---\nid: note-1\ntitle: Test\ntype: inbox\n---\nHello",
        )
        handler._schedule(str(note_path), "create")
        _wait_for_debounce()

        mock_index.reindex_note.assert_called_once()
        mock_graph.update_note.assert_called_once()
        note = mock_index.reindex_note.call_args[0][0]
        assert note.id == "note-1"
        assert note.title == "Test"


class TestModifyEvent:
    def test_modify_triggers_reindex(self, vault_dir, mock_index, mock_graph, handler):
        """Modifying a .md file triggers reindex_note and update_note."""
        note_path = _make_note(
            vault_dir,
            "00-inbox",
            "test-note.md",
            "---\nid: note-2\ntitle: Modified\ntype: inbox\n---\nUpdated content",
        )
        handler._schedule(str(note_path), "modify")
        _wait_for_debounce()

        mock_index.reindex_note.assert_called_once()
        mock_graph.update_note.assert_called_once()
        note = mock_index.reindex_note.call_args[0][0]
        assert note.title == "Modified"


class TestDeleteEvent:
    def test_delete_triggers_remove(self, vault_dir, mock_index, mock_graph, handler):
        """Deleting a .md file triggers remove_note on index and graph."""
        note_path = vault_dir / "00-inbox" / "deleted-note.md"
        # Simulate the graph having this node
        mock_graph._graph.nodes = MagicMock(
            return_value=[("note-3", {"path": str(note_path)})]
        )

        handler._schedule(str(note_path), "delete")
        _wait_for_debounce()

        mock_index.remove_note.assert_called_once_with("note-3")
        mock_graph.remove_note.assert_called_once_with("note-3")

    def test_delete_unknown_file_logs_warning(self, vault_dir, mock_index, mock_graph, handler):
        """Deleting a file not in graph logs a warning but doesn't crash."""
        note_path = vault_dir / "00-inbox" / "unknown.md"
        mock_graph._graph.nodes = MagicMock(return_value=[])

        handler._schedule(str(note_path), "delete")
        _wait_for_debounce()

        mock_index.remove_note.assert_not_called()
        mock_graph.remove_note.assert_not_called()


class TestDebounce:
    def test_rapid_events_debounced(self, vault_dir, mock_index, mock_graph, handler):
        """Rapid modifications to the same file only trigger one reindex."""
        note_path = _make_note(
            vault_dir,
            "00-inbox",
            "rapid.md",
            "---\nid: rapid-1\ntitle: Rapid\ntype: inbox\n---\nFinal content",
        )
        # Simulate rapid saves
        handler._schedule(str(note_path), "modify")
        time.sleep(0.1)
        handler._schedule(str(note_path), "modify")
        time.sleep(0.1)
        handler._schedule(str(note_path), "modify")

        _wait_for_debounce()

        # Should only be called once despite 3 rapid events
        assert mock_index.reindex_note.call_count == 1

    def test_different_files_not_merged(self, vault_dir, mock_index, mock_graph, handler):
        """Events for different files are both processed."""
        note1 = _make_note(
            vault_dir,
            "00-inbox",
            "file1.md",
            "---\nid: f1\ntitle: File1\ntype: inbox\n---\nOne",
        )
        note2 = _make_note(
            vault_dir,
            "00-inbox",
            "file2.md",
            "---\nid: f2\ntitle: File2\ntype: inbox\n---\nTwo",
        )
        handler._schedule(str(note1), "modify")
        handler._schedule(str(note2), "modify")

        _wait_for_debounce()

        assert mock_index.reindex_note.call_count == 2


class TestIgnorePatterns:
    def test_ignores_non_md_files(self, handler):
        """Non-.md files are ignored."""
        assert handler._should_ignore("/vault/note.txt") is True
        assert handler._should_ignore("/vault/image.png") is True

    def test_ignores_temp_files(self, vault_dir, handler):
        """Temp file patterns are ignored."""
        assert handler._should_ignore(str(vault_dir / "note.md~")) is True

    def test_ignores_obsidian_dir(self, vault_dir, handler):
        """Files inside .obsidian directory are ignored."""
        assert handler._should_ignore(str(vault_dir / ".obsidian" / "workspace.md")) is True

    def test_ignores_templates_dir(self, vault_dir, handler):
        """Files inside _templates directory are ignored."""
        assert handler._should_ignore(str(vault_dir / "_templates" / "inbox.md")) is True

    def test_accepts_normal_md(self, vault_dir, handler):
        """Normal .md files in vault folders are accepted."""
        assert handler._should_ignore(str(vault_dir / "00-inbox" / "note.md")) is False


class TestVaultWatcher:
    def test_start_stop(self, vault_dir, mock_index, mock_graph):
        """Watcher can start and stop without error."""
        watcher = VaultWatcher(vault_dir, mock_index, mock_graph)
        watcher.start()
        time.sleep(0.1)
        watcher.stop()
