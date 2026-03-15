"""Tests for MCP search and admin tools."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.capture.draft import DraftManager
from cortex.config import CortexConfig
from cortex.index.lexical import LexicalIndex
from cortex.index.manager import IndexManager
from cortex.mcp.server import (
    get_note,
    init_server,
    mcp_capture_thought,
    rebuild_index,
    search_vault,
    vault_stats,
)
from cortex.vault.manager import VaultManager, scaffold_vault
from cortex.vault.parser import Note


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
def sample_notes(vault_dir: Path) -> list[Path]:
    """Create sample notes in the vault for testing."""
    notes = []

    # Inbox note
    inbox = vault_dir / "00-inbox" / "thought.md"
    inbox.write_text(
        "---\nid: note-001\ntitle: Python Tips\ntype: inbox\ntags: [python]\nstatus: active\n---\n\n"
        "Python is a great language for data science and machine learning.\n",
        encoding="utf-8",
    )
    notes.append(inbox)

    # Concept note
    concept = vault_dir / "20-concepts" / "testing.md"
    concept.write_text(
        "---\nid: note-002\ntitle: Unit Testing\ntype: concept\ntags: [testing, code]\nstatus: active\n---\n\n"
        "Unit testing ensures code correctness. Use pytest for Python projects.\n",
        encoding="utf-8",
    )
    notes.append(concept)

    # Task note
    task = vault_dir / "02-tasks" / "review.md"
    task.write_text(
        "---\nid: note-003\ntitle: Review PR\ntype: task\ntags: [review]\nstatus: active\n---\n\n"
        "Review the pull request for the new search feature.\n",
        encoding="utf-8",
    )
    notes.append(task)

    return notes


@pytest.fixture()
def lexical_index(tmp_path: Path, vault: VaultManager, sample_notes) -> LexicalIndex:
    """Create a LexicalIndex with sample notes indexed."""
    idx = LexicalIndex(tmp_path / "test.duckdb")
    notes = vault.scan_vault()
    idx.rebuild(notes)
    return idx


@pytest.fixture()
def mock_index(lexical_index: LexicalIndex) -> IndexManager:
    """IndexManager with real lexical index but mocked semantic index."""
    idx = MagicMock(spec=IndexManager)
    idx.lexical = lexical_index
    # Mock semantic to return empty results
    idx.semantic = MagicMock()
    idx.semantic.search.return_value = []
    return idx


@pytest.fixture()
def server(config: CortexConfig, vault: VaultManager, mock_index: IndexManager):
    drafts = DraftManager(config.draft.drafts_dir)
    return init_server(config=config, vault=vault, drafts=drafts, index=mock_index)


# ---------------------------------------------------------------------------
# search_vault
# ---------------------------------------------------------------------------


class TestSearchVault:
    def test_search_returns_results(self, server, sample_notes):
        result = search_vault(query="Python")
        assert "results" in result
        assert result["total"] >= 1
        assert result["query"] == "Python"

    def test_search_returns_context(self, server, sample_notes):
        result = search_vault(query="testing")
        assert "context" in result
        assert "explanation" in result

    def test_search_with_limit(self, server, sample_notes):
        result = search_vault(query="Python", limit=1)
        assert result["total"] <= 1

    def test_search_with_note_type_filter(self, server, sample_notes):
        result = search_vault(query="Python testing review", note_type="concept")
        for r in result["results"]:
            assert r["note_type"] == "concept"

    def test_search_empty_results(self, server, sample_notes):
        result = search_vault(query="xyznonexistent99999")
        assert result["total"] == 0
        assert result["results"] == []

    def test_search_without_index_returns_error(self, config, vault):
        """When no index is provided, search returns an error."""
        drafts = DraftManager(config.draft.drafts_dir)
        init_server(config=config, vault=vault, drafts=drafts, index=None)
        result = search_vault(query="test")
        assert "error" in result

    def test_search_result_fields(self, server, sample_notes):
        result = search_vault(query="Python")
        if result["results"]:
            r = result["results"][0]
            assert "note_id" in r
            assert "title" in r
            assert "score" in r
            assert "matched_by" in r


# ---------------------------------------------------------------------------
# get_note
# ---------------------------------------------------------------------------


class TestGetNote:
    def test_get_existing_note(self, server, sample_notes):
        result = get_note(note_id="note-001")
        assert result["note_id"] == "note-001"
        assert result["title"] == "Python Tips"
        assert "Python" in result["content"]
        assert "python" in result["tags"]

    def test_get_note_returns_metadata(self, server, sample_notes):
        result = get_note(note_id="note-002")
        assert result["note_type"] == "concept"
        assert "path" in result

    def test_get_nonexistent_note(self, server):
        result = get_note(note_id="nonexistent-id")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_get_note_without_vault(self, config):
        """When vault is not initialized, returns error."""
        import cortex.mcp.server as srv
        old_vault = srv._vault
        srv._vault = None
        try:
            result = get_note(note_id="any-id")
            assert "error" in result
        finally:
            srv._vault = old_vault


# ---------------------------------------------------------------------------
# rebuild_index
# ---------------------------------------------------------------------------


class TestRebuildIndex:
    def test_rebuild_returns_status(self, server, sample_notes):
        result = rebuild_index()
        assert result["status"] == "rebuilt"
        assert result["notes_indexed"] == 3
        assert "timestamp" in result

    def test_rebuild_without_index_returns_error(self, config, vault):
        drafts = DraftManager(config.draft.drafts_dir)
        init_server(config=config, vault=vault, drafts=drafts, index=None)
        result = rebuild_index()
        assert "error" in result


# ---------------------------------------------------------------------------
# vault_stats
# ---------------------------------------------------------------------------


class TestVaultStats:
    def test_stats_returns_counts(self, server, sample_notes):
        result = vault_stats()
        assert result["total_notes"] == 3
        assert "inbox" in result["by_type"]
        assert "concept" in result["by_type"]
        assert "task" in result["by_type"]

    def test_stats_includes_index_info(self, server, sample_notes):
        result = vault_stats()
        assert "index" in result
        assert "lexical_notes" in result["index"]
        assert "semantic_chunks" in result["index"]

    def test_stats_last_rebuild_initially_none(self, server, sample_notes):
        import cortex.mcp.server as srv
        srv._last_rebuild = None
        result = vault_stats()
        assert result["last_rebuild"] is None

    def test_stats_last_rebuild_after_rebuild(self, server, sample_notes):
        rebuild_index()
        result = vault_stats()
        assert result["last_rebuild"] is not None

    def test_stats_empty_vault(self, config, vault_dir):
        """Stats on an empty vault returns zero counts."""
        vault = VaultManager(vault_dir, config)
        drafts = DraftManager(config.draft.drafts_dir)
        init_server(config=config, vault=vault, drafts=drafts, index=None)
        result = vault_stats()
        assert result["total_notes"] == 0
        assert result["by_type"] == {}


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_search_clear_error_on_missing_index(self, config, vault):
        drafts = DraftManager(config.draft.drafts_dir)
        init_server(config=config, vault=vault, drafts=drafts, index=None)
        result = search_vault(query="test")
        assert "error" in result
        assert "index" in result["error"].lower()

    def test_get_note_clear_error_on_not_found(self, server):
        result = get_note(note_id="does-not-exist")
        assert "error" in result
        assert "not found" in result["error"].lower()
