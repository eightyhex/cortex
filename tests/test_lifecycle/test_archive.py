"""Tests for LifecycleManager archive/unarchive flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.capture.draft import DraftManager
from cortex.config import CortexConfig
from cortex.lifecycle.manager import LifecycleManager
from cortex.vault.manager import VaultManager


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a minimal vault with one note."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "20-concepts").mkdir()
    return vault_dir


@pytest.fixture
def vault(tmp_vault):
    config = CortexConfig(vault={"path": str(tmp_vault)})
    return VaultManager(tmp_vault, config)


@pytest.fixture
def draft_mgr(tmp_path):
    return DraftManager(tmp_path / "drafts")


@pytest.fixture
def mock_index():
    return MagicMock()


@pytest.fixture
def mock_graph():
    mg = MagicMock()
    mg.graph = MagicMock()
    return mg


def _create_note(vault_dir: Path, note_id: str = "note-1", status: str = "active") -> Path:
    note_path = vault_dir / "20-concepts" / f"{note_id}.md"
    note_path.write_text(
        f"""---
id: {note_id}
title: Test Note
type: concept
created: "2026-01-01T00:00:00+00:00"
modified: "2026-01-01T00:00:00+00:00"
tags:
  - test
status: {status}
---

Some content.
""",
        encoding="utf-8",
    )
    return note_path


class TestArchiveNote:
    """Tests for LifecycleManager.archive_note()."""

    def test_archive_sets_status(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """archive_note sets status to archived."""
        _create_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        result = lm.archive_note("note-1")

        assert result.status == "archived"

    def test_archive_sets_archived_date(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """archive_note sets archived_date in frontmatter."""
        _create_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        result = lm.archive_note("note-1")

        assert result.frontmatter.get("archived_date")

    def test_archive_reindexes(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """archive_note re-indexes the note."""
        _create_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        lm.archive_note("note-1")

        mock_index.reindex_note.assert_called_once()
        mock_graph.update_note.assert_called_once()

    def test_archive_persists_to_disk(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """archive_note persists the change to the vault file."""
        _create_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        lm.archive_note("note-1")

        # Re-read from disk
        reloaded = vault.get_note("note-1")
        assert reloaded.status == "archived"


class TestUnarchiveNote:
    """Tests for LifecycleManager.unarchive_note()."""

    def test_unarchive_restores_active(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """unarchive_note restores status to active."""
        _create_note(tmp_vault, status="archived")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        result = lm.unarchive_note("note-1")

        assert result.status == "active"

    def test_unarchive_clears_archived_date(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """unarchive_note clears the archived_date."""
        _create_note(tmp_vault, status="archived")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        result = lm.unarchive_note("note-1")

        # archived_date should be empty/cleared
        ad = result.frontmatter.get("archived_date", "")
        assert not ad or ad == ""

    def test_unarchive_reindexes(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """unarchive_note re-indexes the note."""
        _create_note(tmp_vault, status="archived")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        lm.unarchive_note("note-1")

        mock_index.reindex_note.assert_called_once()
        mock_graph.update_note.assert_called_once()

    def test_archive_then_unarchive_roundtrip(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """Archiving then unarchiving returns note to active state."""
        _create_note(tmp_vault)
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        lm.archive_note("note-1")
        result = lm.unarchive_note("note-1")

        assert result.status == "active"
