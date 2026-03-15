"""Tests for LifecycleManager supersede flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import networkx as nx
import pytest

from cortex.capture.draft import DraftManager
from cortex.config import CortexConfig
from cortex.lifecycle.manager import LifecycleManager
from cortex.vault.manager import VaultManager


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a minimal vault with folders."""
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
    """Create a mock GraphManager with a real NetworkX graph."""
    mg = MagicMock()
    mg.graph = nx.MultiDiGraph()
    return mg


def _create_note(vault_dir: Path, note_id: str, title: str = "Test Note") -> Path:
    note_path = vault_dir / "20-concepts" / f"{note_id}.md"
    note_path.write_text(
        f"""---
id: {note_id}
title: {title}
type: concept
created: "2026-01-01T00:00:00+00:00"
modified: "2026-01-01T00:00:00+00:00"
tags:
  - test
status: active
---

Content of {title}.
""",
        encoding="utf-8",
    )
    return note_path


class TestSupersedeNote:
    """Tests for LifecycleManager.supersede_note()."""

    def test_supersede_sets_old_note_status(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """supersede_note sets old note status to superseded."""
        _create_note(tmp_vault, "old-note", "Old Note")
        _create_note(tmp_vault, "new-note", "New Note")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        old, new = lm.supersede_note("old-note", "new-note")

        assert old.status == "superseded"

    def test_supersede_sets_bidirectional_links(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """supersede_note sets superseded_by on old and supersedes on new."""
        _create_note(tmp_vault, "old-note", "Old Note")
        _create_note(tmp_vault, "new-note", "New Note")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        old, new = lm.supersede_note("old-note", "new-note")

        assert old.frontmatter["superseded_by"] == "new-note"
        assert new.frontmatter["supersedes"] == "old-note"

    def test_supersede_adds_graph_edge(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """supersede_note creates a SUPERSEDES edge in the graph."""
        _create_note(tmp_vault, "old-note", "Old Note")
        _create_note(tmp_vault, "new-note", "New Note")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        lm.supersede_note("old-note", "new-note")

        # Check the graph has the SUPERSEDES edge
        assert mock_graph.graph.has_edge("new-note", "old-note")

    def test_supersede_reindexes_both(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """supersede_note re-indexes both notes."""
        _create_note(tmp_vault, "old-note", "Old Note")
        _create_note(tmp_vault, "new-note", "New Note")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        lm.supersede_note("old-note", "new-note")

        assert mock_index.reindex_note.call_count == 2
        # graph.update_note called for both
        assert mock_graph.update_note.call_count == 2

    def test_supersede_persists_to_disk(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """supersede_note persists changes to vault files."""
        _create_note(tmp_vault, "old-note", "Old Note")
        _create_note(tmp_vault, "new-note", "New Note")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        lm.supersede_note("old-note", "new-note")

        # Re-read from disk
        old_reloaded = vault.get_note("old-note")
        new_reloaded = vault.get_note("new-note")
        assert old_reloaded.status == "superseded"
        assert old_reloaded.frontmatter["superseded_by"] == "new-note"
        assert new_reloaded.frontmatter["supersedes"] == "old-note"

    def test_supersede_preserves_new_note_status(self, vault, mock_index, mock_graph, draft_mgr, tmp_vault):
        """supersede_note keeps the new note as active."""
        _create_note(tmp_vault, "old-note", "Old Note")
        _create_note(tmp_vault, "new-note", "New Note")
        lm = LifecycleManager(vault, mock_index, mock_graph, draft_mgr)

        old, new = lm.supersede_note("old-note", "new-note")

        assert new.status == "active"
