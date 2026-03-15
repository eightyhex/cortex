"""Tests for MCP lifecycle tools: edit, archive, unarchive, supersede, detect_stale."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import networkx as nx
import pytest

from cortex.capture.draft import DraftManager
from cortex.config import CortexConfig
from cortex.graph.manager import GraphManager
from cortex.index.manager import IndexManager
from cortex.lifecycle.manager import LifecycleManager
from cortex.mcp.server import (
    archive_note,
    approve_edit,
    detect_stale,
    edit_note,
    init_server,
    supersede_note,
    unarchive_note,
)
from cortex.vault.manager import VaultManager, scaffold_vault


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    scaffold_vault(vault)
    return vault


@pytest.fixture()
def config(tmp_path: Path, vault_dir: Path) -> CortexConfig:
    return CortexConfig(
        vault={"path": str(vault_dir)},
        draft={"drafts_dir": str(tmp_path / "drafts")},
        index={
            "db_path": str(tmp_path / "cortex.duckdb"),
            "embeddings_path": str(tmp_path / "embeddings"),
        },
    )


@pytest.fixture()
def vault(vault_dir: Path, config: CortexConfig) -> VaultManager:
    return VaultManager(vault_dir, config)


@pytest.fixture()
def mock_index() -> IndexManager:
    idx = MagicMock(spec=IndexManager)
    idx.lexical = MagicMock()
    idx.semantic = MagicMock()
    idx.semantic.search.return_value = []
    return idx


@pytest.fixture()
def mock_graph() -> GraphManager:
    g = MagicMock(spec=GraphManager)
    g.graph = nx.MultiDiGraph()
    return g


@pytest.fixture()
def sample_notes(vault_dir: Path) -> dict[str, Path]:
    """Create sample notes for lifecycle testing."""
    notes = {}

    concept = vault_dir / "20-concepts" / "caching.md"
    concept.write_text(
        "---\nid: note-cache-1\ntitle: Caching Strategies\ntype: concept\n"
        "tags: [caching, distributed]\nstatus: active\n---\n\n"
        "Caching is essential for distributed systems.\n",
        encoding="utf-8",
    )
    notes["concept"] = concept

    concept2 = vault_dir / "20-concepts" / "caching-v2.md"
    concept2.write_text(
        "---\nid: note-cache-2\ntitle: Caching Strategies v2\ntype: concept\n"
        "tags: [caching, distributed]\nstatus: active\n---\n\n"
        "Updated caching strategies for distributed systems.\n",
        encoding="utf-8",
    )
    notes["concept2"] = concept2

    inbox = vault_dir / "00-inbox" / "stale-thought.md"
    old_date = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
    inbox.write_text(
        f"---\nid: note-stale-1\ntitle: Old Thought\ntype: inbox\n"
        f"tags: [random]\nstatus: active\nmodified: {old_date}\n---\n\n"
        f"An old inbox thought.\n",
        encoding="utf-8",
    )
    notes["stale_inbox"] = inbox

    return notes


@pytest.fixture()
def server(
    config: CortexConfig,
    vault: VaultManager,
    mock_index: IndexManager,
    mock_graph: GraphManager,
):
    drafts = DraftManager(config.draft.drafts_dir)
    return init_server(
        config=config, vault=vault, drafts=drafts, index=mock_index, graph=mock_graph
    )


# ---------------------------------------------------------------------------
# edit_note
# ---------------------------------------------------------------------------


class TestEditNote:
    def test_edit_returns_draft_with_diff(self, server, sample_notes):
        result = edit_note(note_id="note-cache-1", changes={"title": "New Title"})
        assert "draft_id" in result
        assert "diff" in result
        assert "preview" in result
        assert result["note_id"] == "note-cache-1"

    def test_edit_nonexistent_note(self, server):
        result = edit_note(note_id="nonexistent", changes={"title": "X"})
        assert "error" in result

    def test_approve_edit_commits(self, server, sample_notes, mock_index, mock_graph):
        # Start edit
        edit_result = edit_note(
            note_id="note-cache-1", changes={"content": "Updated content."}
        )
        draft_id = edit_result["draft_id"]

        # Approve
        result = approve_edit(draft_id=draft_id)
        assert result["status"] == "committed"
        assert result["note_id"] == "note-cache-1"

        # Verify reindex was called
        mock_index.reindex_note.assert_called()

    def test_approve_edit_invalid_draft(self, server):
        result = approve_edit(draft_id="nonexistent-draft")
        assert "error" in result


# ---------------------------------------------------------------------------
# archive_note / unarchive_note
# ---------------------------------------------------------------------------


class TestArchiveNote:
    def test_archive_returns_status(self, server, sample_notes, mock_index):
        result = archive_note(note_id="note-cache-1")
        assert result["status"] == "archived"
        assert result["note_id"] == "note-cache-1"
        mock_index.reindex_note.assert_called()

    def test_archive_nonexistent_note(self, server):
        result = archive_note(note_id="nonexistent")
        assert "error" in result

    def test_unarchive_returns_status(self, server, sample_notes, mock_index):
        # First archive
        archive_note(note_id="note-cache-1")
        # Then unarchive
        result = unarchive_note(note_id="note-cache-1")
        assert result["status"] == "active"
        assert result["note_id"] == "note-cache-1"

    def test_unarchive_nonexistent_note(self, server):
        result = unarchive_note(note_id="nonexistent")
        assert "error" in result


# ---------------------------------------------------------------------------
# supersede_note
# ---------------------------------------------------------------------------


class TestSupersedeNote:
    def test_supersede_returns_status(self, server, sample_notes, mock_index):
        result = supersede_note(
            old_note_id="note-cache-1", new_note_id="note-cache-2"
        )
        assert result["old_status"] == "superseded"
        assert result["old_note_id"] == "note-cache-1"
        assert result["new_note_id"] == "note-cache-2"
        assert result["superseded_by"] == "note-cache-2"

    def test_supersede_nonexistent_note(self, server):
        result = supersede_note(old_note_id="nonexistent", new_note_id="also-missing")
        assert "error" in result

    def test_supersede_reindexes_both(self, server, sample_notes, mock_index):
        supersede_note(old_note_id="note-cache-1", new_note_id="note-cache-2")
        assert mock_index.reindex_note.call_count >= 2


# ---------------------------------------------------------------------------
# detect_stale
# ---------------------------------------------------------------------------


class TestDetectStale:
    def test_detect_stale_returns_candidates(self, server, sample_notes):
        result = detect_stale()
        assert "total_stale" in result
        assert "candidates" in result
        assert isinstance(result["candidates"], list)

    def test_detect_stale_finds_old_inbox(self, server, sample_notes):
        result = detect_stale()
        stale_ids = [c["note_id"] for c in result["candidates"]]
        assert "note-stale-1" in stale_ids

    def test_detect_stale_candidate_fields(self, server, sample_notes):
        result = detect_stale()
        if result["candidates"]:
            c = result["candidates"][0]
            assert "note_id" in c
            assert "title" in c
            assert "staleness_score" in c
            assert "reasons" in c
            assert "suggested_action" in c


# ---------------------------------------------------------------------------
# Error handling — lifecycle not initialized
# ---------------------------------------------------------------------------


class TestLifecycleErrors:
    def test_edit_without_lifecycle(self, config, vault):
        """When graph/index not provided, lifecycle tools return errors."""
        drafts = DraftManager(config.draft.drafts_dir)
        init_server(config=config, vault=vault, drafts=drafts, index=None, graph=None)
        result = edit_note(note_id="any", changes={})
        assert "error" in result

    def test_archive_without_lifecycle(self, config, vault):
        drafts = DraftManager(config.draft.drafts_dir)
        init_server(config=config, vault=vault, drafts=drafts, index=None, graph=None)
        result = archive_note(note_id="any")
        assert "error" in result

    def test_detect_stale_without_graph(self, config, vault):
        drafts = DraftManager(config.draft.drafts_dir)
        init_server(config=config, vault=vault, drafts=drafts, index=None, graph=None)
        result = detect_stale()
        assert "error" in result
