"""Tests for LifecycleManager edit flow."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.capture.draft import DraftManager, NoteDraft
from cortex.config import CortexConfig
from cortex.lifecycle.manager import LifecycleManager
from cortex.vault.manager import VaultManager
from cortex.vault.parser import Note, parse_note


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a minimal vault with one note."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "20-concepts").mkdir()
    return vault_dir


@pytest.fixture
def vault(tmp_vault):
    """Create a VaultManager."""
    config = CortexConfig(vault={"path": str(tmp_vault)})
    return VaultManager(tmp_vault, config)


@pytest.fixture
def draft_mgr(tmp_path):
    """Create a DraftManager."""
    return DraftManager(tmp_path / "drafts")


@pytest.fixture
def mock_index():
    """Create a mock IndexManager."""
    idx = MagicMock()
    return idx


@pytest.fixture
def mock_graph():
    """Create a mock GraphManager."""
    graph = MagicMock()
    return graph


def _create_test_note(vault_dir: Path, note_id: str = "test-note-1") -> Path:
    """Write a test note file and return its path."""
    note_path = vault_dir / "20-concepts" / "test-note.md"
    note_path.write_text(
        f"""---
id: {note_id}
title: Original Title
type: concept
created: "2026-01-01T00:00:00+00:00"
modified: "2026-01-01T00:00:00+00:00"
tags:
  - python
  - testing
status: active
---

Original content here.
""",
        encoding="utf-8",
    )
    return note_path


class TestStartEdit:
    """Tests for LifecycleManager.start_edit()."""

    def test_start_edit_creates_draft(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """start_edit returns a NoteDraft with the proposed changes."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"content": "Updated content."})

        assert isinstance(draft, NoteDraft)
        assert draft.content == "Updated content."
        assert draft.title == "Original Title"
        assert draft.frontmatter["_edit_note_id"] == "test-note-1"

    def test_start_edit_includes_diff(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """start_edit includes a diff showing what changed."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"content": "New content."})

        diff = draft.frontmatter["_diff"]
        assert "---" in diff or "+++" in diff or "-Original" in diff
        assert "New content." in diff

    def test_start_edit_preserves_title(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """start_edit preserves the original title when not changed."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"content": "Changed"})

        assert draft.title == "Original Title"
        assert draft.frontmatter["title"] == "Original Title"

    def test_start_edit_changes_title(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """start_edit updates the title when specified in changes."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"title": "New Title"})

        assert draft.title == "New Title"
        assert draft.frontmatter["title"] == "New Title"

    def test_start_edit_changes_tags(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """start_edit updates tags when specified in changes."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"tags": ["rust", "concurrency"]})

        assert draft.frontmatter["tags"] == ["rust", "concurrency"]

    def test_start_edit_persists_draft(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """start_edit persists the draft via DraftManager."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"content": "Saved"})

        # Should be retrievable
        loaded = draft_mgr.get_draft(draft.draft_id)
        assert loaded.content == "Saved"


class TestCommitEdit:
    """Tests for LifecycleManager.commit_edit()."""

    def test_commit_edit_updates_vault(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """commit_edit writes the changes to the vault file."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"content": "Committed content."})
        updated = lm.commit_edit(draft.draft_id)

        assert updated.content == "Committed content."
        assert updated.title == "Original Title"

    def test_commit_edit_reindexes(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """commit_edit re-indexes the note in all stores."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"content": "Reindexed."})
        lm.commit_edit(draft.draft_id)

        mock_index.reindex_note.assert_called_once()
        mock_graph.update_note.assert_called_once()

    def test_commit_edit_updates_modified(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """commit_edit bumps the modified timestamp."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"content": "Timestamped."})
        updated = lm.commit_edit(draft.draft_id)

        # Modified should be after the original 2026-01-01
        assert updated.modified > datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_commit_edit_removes_draft(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """commit_edit cleans up the draft file."""
        _create_test_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        draft = lm.start_edit("test-note-1", {"content": "Cleaned up."})
        draft_id = draft.draft_id
        lm.commit_edit(draft_id)

        with pytest.raises(KeyError):
            draft_mgr.get_draft(draft_id)

    def test_commit_edit_not_edit_draft_raises(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """commit_edit raises ValueError if draft is not an edit draft."""
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        # Create a regular (non-edit) draft
        regular_draft = draft_mgr.create_draft("concept", "Test", "Content")

        with pytest.raises(ValueError, match="not an edit draft"):
            lm.commit_edit(regular_draft.draft_id)
