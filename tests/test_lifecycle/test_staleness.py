"""Tests for staleness detection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import networkx as nx
import pytest

from cortex.config import CortexConfig, LifecycleConfig
from cortex.lifecycle.staleness import StaleCandidate, detect_stale_notes
from cortex.vault.manager import VaultManager


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
    """Minimal GraphManager stand-in for staleness tests."""

    def __init__(self):
        self.graph = nx.MultiDiGraph()

    def add_link(self, source_id: str, target_id: str):
        if not self.graph.has_node(source_id):
            self.graph.add_node(source_id)
        if not self.graph.has_node(target_id):
            self.graph.add_node(target_id)
        self.graph.add_edge(source_id, target_id, rel_type="LINKS_TO")


def _write_note(
    vault_dir: Path,
    folder: str,
    note_id: str,
    note_type: str,
    modified: datetime,
    *,
    status: str = "active",
    evergreen: bool = False,
    tags: list[str] | None = None,
) -> Path:
    """Write a note file to the vault."""
    fm_lines = [
        "---",
        f"id: {note_id}",
        f"title: Test {note_id}",
        f"type: {note_type}",
        f"created: {modified.isoformat()}",
        f"modified: {modified.isoformat()}",
        f"status: {status}",
    ]
    if evergreen:
        fm_lines.append("evergreen: true")
    if tags:
        fm_lines.append(f"tags: [{', '.join(tags)}]")
    fm_lines.append("---")
    fm_lines.append("")
    fm_lines.append("Some content.")

    path = vault_dir / folder / f"{note_id}.md"
    path.write_text("\n".join(fm_lines))
    return path


class TestStalenessDetection:
    def test_stale_inbox_note(self, tmp_vault, vault, config):
        """Inbox note older than 30 days is detected as stale."""
        old = datetime.now(timezone.utc) - timedelta(days=45)
        _write_note(tmp_vault, "00-inbox", "inbox-1", "inbox", old)

        graph = FakeGraphManager()
        results = detect_stale_notes(vault, graph, config)

        assert len(results) >= 1
        candidate = next(c for c in results if c.note.id == "inbox-1")
        assert candidate.staleness_score > 0
        assert any("30d" in r for r in candidate.reasons)

    def test_fresh_note_not_stale(self, tmp_vault, vault, config):
        """A recently modified note should not be detected as stale."""
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        _write_note(tmp_vault, "20-concepts", "fresh-1", "concept", recent)

        graph = FakeGraphManager()
        graph.graph.add_node("fresh-1")
        graph.add_link("other-note", "fresh-1")  # has inbound link

        results = detect_stale_notes(vault, graph, config)
        ids = [c.note.id for c in results]
        assert "fresh-1" not in ids

    def test_evergreen_exempt(self, tmp_vault, vault, config):
        """Notes with evergreen: true are exempt from staleness."""
        old = datetime.now(timezone.utc) - timedelta(days=400)
        _write_note(tmp_vault, "30-permanent", "perm-1", "permanent", old, evergreen=True)

        graph = FakeGraphManager()
        results = detect_stale_notes(vault, graph, config)
        ids = [c.note.id for c in results]
        assert "perm-1" not in ids

    def test_orphan_detection(self, tmp_vault, vault, config):
        """Notes with no inbound links get an orphan penalty."""
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        _write_note(tmp_vault, "20-concepts", "orphan-1", "concept", recent)

        graph = FakeGraphManager()
        # orphan-1 has no inbound links
        results = detect_stale_notes(vault, graph, config)

        assert len(results) >= 1
        candidate = next(c for c in results if c.note.id == "orphan-1")
        assert any("Orphan" in r for r in candidate.reasons)
        assert candidate.staleness_score >= 0.5

    def test_sorted_by_staleness_score(self, tmp_vault, vault, config):
        """Results are sorted most stale first."""
        very_old = datetime.now(timezone.utc) - timedelta(days=200)
        somewhat_old = datetime.now(timezone.utc) - timedelta(days=50)

        _write_note(tmp_vault, "00-inbox", "less-stale", "inbox", somewhat_old)
        _write_note(tmp_vault, "10-sources", "more-stale", "source", very_old)

        graph = FakeGraphManager()
        results = detect_stale_notes(vault, graph, config)

        assert len(results) >= 2
        scores = [c.staleness_score for c in results]
        assert scores == sorted(scores, reverse=True)

    def test_archived_notes_skipped(self, tmp_vault, vault, config):
        """Archived notes are not flagged as stale."""
        old = datetime.now(timezone.utc) - timedelta(days=100)
        _write_note(tmp_vault, "20-concepts", "archived-1", "concept", old, status="archived")

        graph = FakeGraphManager()
        results = detect_stale_notes(vault, graph, config)
        ids = [c.note.id for c in results]
        assert "archived-1" not in ids

    def test_suggested_action_archive(self, tmp_vault, vault, config):
        """Very stale notes get 'archive' as suggested action."""
        very_old = datetime.now(timezone.utc) - timedelta(days=800)
        _write_note(tmp_vault, "30-permanent", "ancient-1", "permanent", very_old)

        graph = FakeGraphManager()
        results = detect_stale_notes(vault, graph, config)

        candidate = next(c for c in results if c.note.id == "ancient-1")
        assert candidate.suggested_action == "archive"

    def test_inbox_suggested_action_categorize(self, tmp_vault, vault, config):
        """Stale inbox notes get 'categorize' as suggested action."""
        old = datetime.now(timezone.utc) - timedelta(days=45)
        _write_note(tmp_vault, "00-inbox", "inbox-cat", "inbox", old)

        graph = FakeGraphManager()
        graph.graph.add_node("inbox-cat")
        graph.add_link("some-note", "inbox-cat")  # has inbound link, so only age-stale

        results = detect_stale_notes(vault, graph, config)
        candidate = next(c for c in results if c.note.id == "inbox-cat")
        assert candidate.suggested_action == "categorize"
