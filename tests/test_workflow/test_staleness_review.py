"""Tests for staleness review workflow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import networkx as nx
import pytest

from cortex.config import CortexConfig, LifecycleConfig
from cortex.vault.manager import VaultManager
from cortex.workflow.staleness_review import staleness_review


@pytest.fixture
def tmp_vault(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    for folder in ("00-inbox", "02-tasks", "10-sources", "20-concepts", "30-permanent"):
        (vault_dir / folder).mkdir()
    return vault_dir


@pytest.fixture
def vault(tmp_vault):
    config = CortexConfig(vault={"path": str(tmp_vault)})
    return VaultManager(tmp_vault, config)


@pytest.fixture
def config():
    return LifecycleConfig()


class FakeGraphManager:
    """Minimal GraphManager stand-in."""

    def __init__(self):
        self.graph = nx.MultiDiGraph()

    def add_link(self, source_id: str, target_id: str):
        if not self.graph.has_node(source_id):
            self.graph.add_node(source_id)
        if not self.graph.has_node(target_id):
            self.graph.add_node(target_id)
        self.graph.add_edge(source_id, target_id, rel_type="LINKS_TO")


def _write_note(vault_dir: Path, folder: str, note_id: str, note_type: str, modified: datetime) -> Path:
    """Write a note file to the vault."""
    fm = f"""---
id: {note_id}
title: Test {note_id}
type: {note_type}
created: {modified.isoformat()}
modified: {modified.isoformat()}
status: active
---

Some content.
"""
    path = vault_dir / folder / f"{note_id}.md"
    path.write_text(fm)
    return path


class TestStalenessReview:
    """Tests for staleness_review()."""

    def test_returns_stale_candidates(self, tmp_vault, vault, config):
        """Returns StaleCandidate list for stale notes."""
        old = datetime.now(timezone.utc) - timedelta(days=45)
        _write_note(tmp_vault, "00-inbox", "stale-1", "inbox", old)

        graph = FakeGraphManager()
        results = staleness_review(vault, graph, config)

        assert len(results) >= 1
        candidate = next(c for c in results if c.note.id == "stale-1")
        assert candidate.staleness_score > 0
        assert candidate.suggested_action in ("archive", "categorize", "review")

    def test_empty_vault_returns_empty(self, vault, config):
        """Returns empty list for vaults with no stale notes."""
        graph = FakeGraphManager()
        results = staleness_review(vault, graph, config)
        assert results == []

    def test_sorted_by_score(self, tmp_vault, vault, config):
        """Results are sorted by staleness_score descending."""
        very_old = datetime.now(timezone.utc) - timedelta(days=200)
        somewhat_old = datetime.now(timezone.utc) - timedelta(days=50)

        _write_note(tmp_vault, "00-inbox", "less-stale", "inbox", somewhat_old)
        _write_note(tmp_vault, "10-sources", "more-stale", "source", very_old)

        graph = FakeGraphManager()
        results = staleness_review(vault, graph, config)

        assert len(results) >= 2
        scores = [c.staleness_score for c in results]
        assert scores == sorted(scores, reverse=True)


class TestMCPStalenessReview:
    """Test the MCP tool wrapper."""

    def test_mcp_tool_returns_candidates(self, tmp_vault):
        """The mcp_staleness_review tool returns formatted candidates."""
        from cortex.mcp.server import init_server, mcp_staleness_review

        config = CortexConfig(vault={"path": str(tmp_vault)})
        v = VaultManager(tmp_vault, config)
        old = datetime.now(timezone.utc) - timedelta(days=45)
        _write_note(tmp_vault, "00-inbox", "stale-mcp", "inbox", old)

        graph = FakeGraphManager()
        init_server(config=config, vault=v, graph=graph)
        result = mcp_staleness_review()

        assert result["total_stale"] >= 1
        ids = [c["note_id"] for c in result["candidates"]]
        assert "stale-mcp" in ids
        assert "suggested_action" in result["candidates"][0]
        assert "path" in result["candidates"][0]
