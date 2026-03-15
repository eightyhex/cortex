"""Tests for GraphManager & graph builder."""

from __future__ import annotations

from dataclasses import field
from datetime import datetime
from pathlib import Path

import networkx as nx
import pytest

from cortex.graph.manager import GraphManager
from cortex.vault.parser import Link, Note


def _make_note(
    note_id: str = "note-1",
    title: str = "Test Note",
    note_type: str = "concept",
    links: list[Link] | None = None,
    tags: list[str] | None = None,
    frontmatter: dict | None = None,
    supersedes: str | None = None,
) -> Note:
    """Create a Note for testing."""
    now = datetime.now()
    return Note(
        id=note_id,
        title=title,
        note_type=note_type,
        path=Path(f"20-concepts/{note_id}.md"),
        content="test content",
        frontmatter=frontmatter or {},
        created=now,
        modified=now,
        tags=tags or [],
        links=links or [],
        status="active",
        supersedes=supersedes,
    )


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    return tmp_path / "graph.graphml"


@pytest.fixture
def sample_notes() -> list[Note]:
    """Three notes with links between them."""
    note_a = _make_note(
        note_id="aaa",
        title="Note A",
        links=[Link(source_id="aaa", target_id="bbb", target_title="Note B", link_type="wikilink")],
    )
    note_b = _make_note(
        note_id="bbb",
        title="Note B",
        links=[Link(source_id="bbb", target_id="ccc", target_title="Note C", link_type="wikilink")],
    )
    note_c = _make_note(note_id="ccc", title="Note C")
    return [note_a, note_b, note_c]


class TestGraphManagerBuild:
    """Tests for build_from_vault."""

    def test_build_creates_nodes(self, graph_path: Path, sample_notes: list[Note]) -> None:
        mgr = GraphManager(graph_path)
        mgr.build_from_vault(sample_notes)

        assert mgr.graph.number_of_nodes() == 3
        assert mgr.graph.has_node("aaa")
        assert mgr.graph.has_node("bbb")
        assert mgr.graph.has_node("ccc")

    def test_build_creates_edges(self, graph_path: Path, sample_notes: list[Note]) -> None:
        mgr = GraphManager(graph_path)
        mgr.build_from_vault(sample_notes)

        assert mgr.graph.has_edge("aaa", "bbb")
        assert mgr.graph.has_edge("bbb", "ccc")
        assert not mgr.graph.has_edge("ccc", "aaa")

    def test_node_attributes(self, graph_path: Path, sample_notes: list[Note]) -> None:
        mgr = GraphManager(graph_path)
        mgr.build_from_vault(sample_notes)

        attrs = mgr.graph.nodes["aaa"]
        assert attrs["node_type"] == "note"
        assert attrs["title"] == "Note A"
        assert attrs["note_type"] == "concept"
        assert "path" in attrs

    def test_edge_attributes(self, graph_path: Path, sample_notes: list[Note]) -> None:
        mgr = GraphManager(graph_path)
        mgr.build_from_vault(sample_notes)

        edge_data = mgr.graph.get_edge_data("aaa", "bbb")
        assert edge_data is not None
        # MultiDiGraph returns dict of {key: attrs}
        rel_types = [d["rel_type"] for d in edge_data.values()]
        assert "LINKS_TO" in rel_types


class TestGraphManagerPersistence:
    """Tests for save/load round-trip."""

    def test_save_load_round_trip(self, graph_path: Path, sample_notes: list[Note]) -> None:
        mgr = GraphManager(graph_path)
        mgr.build_from_vault(sample_notes)
        mgr.save()

        assert graph_path.exists()

        # Load into new manager
        mgr2 = GraphManager(graph_path)
        assert mgr2.graph.number_of_nodes() == 3
        assert mgr2.graph.has_edge("aaa", "bbb")

    def test_save_creates_backup(self, graph_path: Path, sample_notes: list[Note]) -> None:
        mgr = GraphManager(graph_path)
        mgr.build_from_vault(sample_notes)
        mgr.save()  # First save — no backup yet

        mgr.save()  # Second save — backup created
        backup = graph_path.with_suffix(".graphml.bak")
        assert backup.exists()


class TestGraphManagerUpdate:
    """Tests for update_note."""

    def test_update_existing_note(self, graph_path: Path, sample_notes: list[Note]) -> None:
        mgr = GraphManager(graph_path)
        mgr.build_from_vault(sample_notes)

        # Update note A with new title and different link
        updated_a = _make_note(
            note_id="aaa",
            title="Updated Note A",
            links=[Link(source_id="aaa", target_id="ccc", target_title="Note C", link_type="wikilink")],
        )
        mgr.update_note(updated_a)

        assert mgr.graph.nodes["aaa"]["title"] == "Updated Note A"
        # Old edge aaa->bbb removed, new edge aaa->ccc added
        assert not mgr.graph.has_edge("aaa", "bbb")
        assert mgr.graph.has_edge("aaa", "ccc")

    def test_update_adds_new_note(self, graph_path: Path) -> None:
        mgr = GraphManager(graph_path)
        note = _make_note(note_id="new-1", title="Brand New")
        mgr.update_note(note)

        assert mgr.graph.has_node("new-1")
        assert mgr.graph.nodes["new-1"]["title"] == "Brand New"


class TestGraphManagerRemove:
    """Tests for remove_note."""

    def test_remove_node_and_edges(self, graph_path: Path, sample_notes: list[Note]) -> None:
        mgr = GraphManager(graph_path)
        mgr.build_from_vault(sample_notes)

        mgr.remove_note("bbb")

        assert not mgr.graph.has_node("bbb")
        assert not mgr.graph.has_edge("aaa", "bbb")
        assert not mgr.graph.has_edge("bbb", "ccc")
        # Other nodes still exist
        assert mgr.graph.has_node("aaa")
        assert mgr.graph.has_node("ccc")

    def test_remove_nonexistent_is_noop(self, graph_path: Path) -> None:
        mgr = GraphManager(graph_path)
        mgr.remove_note("does-not-exist")  # Should not raise
        assert mgr.graph.number_of_nodes() == 0


class TestGraphBuilderEdgeTypes:
    """Tests for BELONGS_TO_PROJECT and SUPERSEDES edges."""

    def test_belongs_to_project(self, graph_path: Path) -> None:
        note = _make_note(
            note_id="note-p1",
            title="Project Task",
            frontmatter={"project": "cortex"},
        )
        mgr = GraphManager(graph_path)
        mgr.build_from_vault([note])

        project_node_id = "project-cortex"
        assert mgr.graph.has_node(project_node_id)
        assert mgr.graph.nodes[project_node_id]["node_type"] == "project"
        assert mgr.graph.nodes[project_node_id]["title"] == "cortex"

        edge_data = mgr.graph.get_edge_data("note-p1", project_node_id)
        rel_types = [d["rel_type"] for d in edge_data.values()]
        assert "BELONGS_TO_PROJECT" in rel_types

    def test_supersedes_edge(self, graph_path: Path) -> None:
        old_note = _make_note(note_id="old-1", title="Old Version")
        new_note = _make_note(
            note_id="new-1",
            title="New Version",
            supersedes="old-1",
        )
        mgr = GraphManager(graph_path)
        mgr.build_from_vault([old_note, new_note])

        edge_data = mgr.graph.get_edge_data("new-1", "old-1")
        assert edge_data is not None
        rel_types = [d["rel_type"] for d in edge_data.values()]
        assert "SUPERSEDES" in rel_types
