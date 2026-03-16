"""Tests for graph query patterns."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import networkx as nx
import pytest

from cortex.graph.builder import build_graph
from cortex.graph.queries import (
    find_path,
    get_cluster,
    get_neighbors,
    get_project_notes,
    graph_search,
)
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


def _build_chain_graph() -> nx.MultiDiGraph:
    """Build a linear chain: A -> B -> C -> D."""
    notes = [
        _make_note(
            note_id="aaa",
            title="Note A",
            links=[Link(source_id="aaa", target_id="bbb", target_title="B", link_type="wikilink")],
        ),
        _make_note(
            note_id="bbb",
            title="Note B",
            links=[Link(source_id="bbb", target_id="ccc", target_title="C", link_type="wikilink")],
        ),
        _make_note(
            note_id="ccc",
            title="Note C",
            links=[Link(source_id="ccc", target_id="ddd", target_title="D", link_type="wikilink")],
        ),
        _make_note(note_id="ddd", title="Note D"),
    ]
    return build_graph(notes)


def _build_star_graph() -> nx.MultiDiGraph:
    """Build a star: center -> spoke1, spoke2, spoke3."""
    notes = [
        _make_note(
            note_id="center",
            title="Center",
            links=[
                Link(source_id="center", target_id="s1", target_title="S1", link_type="wikilink"),
                Link(source_id="center", target_id="s2", target_title="S2", link_type="wikilink"),
                Link(source_id="center", target_id="s3", target_title="S3", link_type="wikilink"),
            ],
        ),
        _make_note(note_id="s1", title="Spoke 1"),
        _make_note(note_id="s2", title="Spoke 2"),
        _make_note(note_id="s3", title="Spoke 3"),
    ]
    return build_graph(notes)


class TestGetNeighbors:
    """Tests for get_neighbors()."""

    def test_depth_1(self) -> None:
        graph = _build_chain_graph()
        neighbors = get_neighbors(graph, "bbb", depth=1)
        # B connects to A (incoming) and C (outgoing)
        assert set(neighbors) == {"aaa", "ccc"}

    def test_depth_2(self) -> None:
        graph = _build_chain_graph()
        neighbors = get_neighbors(graph, "bbb", depth=2)
        # Depth 2 from B: A, C (depth 1) + D (depth 2 via C)
        assert set(neighbors) == {"aaa", "ccc", "ddd"}

    def test_missing_node(self) -> None:
        graph = _build_chain_graph()
        assert get_neighbors(graph, "nonexistent") == []


class TestFindPath:
    """Tests for find_path()."""

    def test_direct_link(self) -> None:
        graph = _build_chain_graph()
        path = find_path(graph, "aaa", "bbb")
        assert path == ["aaa", "bbb"]

    def test_multi_hop(self) -> None:
        graph = _build_chain_graph()
        path = find_path(graph, "aaa", "ddd")
        assert path == ["aaa", "bbb", "ccc", "ddd"]

    def test_no_path(self) -> None:
        """Disconnected nodes have no path."""
        graph = _build_chain_graph()
        # Add an isolated node
        graph.add_node("isolated", node_type="note", title="Isolated")
        assert find_path(graph, "aaa", "isolated") == []

    def test_missing_node(self) -> None:
        graph = _build_chain_graph()
        assert find_path(graph, "aaa", "nonexistent") == []


class TestGetCluster:
    """Tests for get_cluster()."""

    def test_star_cluster(self) -> None:
        graph = _build_star_graph()
        cluster = get_cluster(graph, "center", max_nodes=20)
        assert set(cluster) == {"s1", "s2", "s3"}

    def test_max_nodes_limit(self) -> None:
        graph = _build_star_graph()
        cluster = get_cluster(graph, "center", max_nodes=2)
        assert len(cluster) == 2

    def test_missing_node(self) -> None:
        graph = _build_star_graph()
        assert get_cluster(graph, "nonexistent") == []


class TestGetProjectNotes:
    """Tests for get_project_notes()."""

    def test_project_members(self) -> None:
        notes = [
            _make_note(note_id="n1", title="Task 1", frontmatter={"project": "alpha"}),
            _make_note(note_id="n2", title="Task 2", frontmatter={"project": "alpha"}),
            _make_note(note_id="n3", title="Other", frontmatter={"project": "beta"}),
        ]
        graph = build_graph(notes)
        members = get_project_notes(graph, "project-alpha")
        assert set(members) == {"n1", "n2"}

    def test_missing_project(self) -> None:
        graph = _build_chain_graph()
        assert get_project_notes(graph, "project-nonexistent") == []


class TestGraphSearch:
    """Tests for graph_search()."""

    def test_expands_seeds(self) -> None:
        graph = _build_chain_graph()
        # Seed with A, should find B (neighbor)
        results = graph_search(graph, ["aaa"], depth=1)
        result_ids = {r.note_id for r in results}
        assert "bbb" in result_ids
        # Seed itself should NOT be in results
        assert "aaa" not in result_ids

    def test_excludes_seeds(self) -> None:
        graph = _build_chain_graph()
        results = graph_search(graph, ["aaa", "bbb"], depth=1)
        result_ids = {r.note_id for r in results}
        assert "aaa" not in result_ids
        assert "bbb" not in result_ids

    def test_score_decays_by_hop(self) -> None:
        graph = _build_chain_graph()
        results = graph_search(graph, ["aaa"], depth=2)
        by_id = {r.note_id: r for r in results}
        # B is 1 hop -> score 1.0, C is 2 hops -> score 0.5
        assert by_id["bbb"].score == pytest.approx(1.0)
        assert by_id["ccc"].score == pytest.approx(0.5)

    def test_skips_project_nodes(self) -> None:
        notes = [
            _make_note(note_id="n1", title="Task", frontmatter={"project": "alpha"}),
        ]
        graph = build_graph(notes)
        results = graph_search(graph, ["n1"], depth=1)
        result_ids = {r.note_id for r in results}
        assert "project-alpha" not in result_ids

    def test_missing_seed_is_skipped(self) -> None:
        graph = _build_chain_graph()
        results = graph_search(graph, ["nonexistent"], depth=1)
        assert results == []

    def test_result_has_search_result_fields(self) -> None:
        graph = _build_chain_graph()
        results = graph_search(graph, ["aaa"], depth=1)
        r = results[0]
        assert r.note_id == "bbb"
        assert r.title == "Note B"
        assert r.note_type == "concept"
        assert r.path != ""

    def test_with_vault_populates_snippets(self, tmp_path: Path) -> None:
        """When vault is provided, graph_search populates snippet from note content."""
        from cortex.config import CortexConfig
        from cortex.vault.manager import VaultManager

        # Create a vault with notes matching the graph
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        for folder in ["20-concepts"]:
            (vault_path / folder).mkdir()

        long_content = "A" * 1200
        notes = []
        for nid, title, content in [
            ("aaa", "Note A", "Content of note A"),
            ("bbb", "Note B", long_content),
            ("ccc", "Note C", "Content of note C"),
            ("ddd", "Note D", "Content of note D"),
        ]:
            note = _make_note(
                note_id=nid,
                title=title,
                links=[Link(source_id=nid, target_id="bbb", target_title="B", link_type="wikilink")]
                if nid == "aaa"
                else [],
            )
            note.content = content
            # Write note file to vault
            fm = f"---\nid: {nid}\ntitle: {title}\ntype: concept\nstatus: active\n---\n{content}"
            (vault_path / f"20-concepts/{nid}.md").write_text(fm)
            notes.append(note)

        graph = build_graph(notes)
        config = CortexConfig(vault={"path": str(vault_path)})
        vault = VaultManager(vault_path, config)

        results = graph_search(graph, ["aaa"], depth=1, vault=vault)
        by_id = {r.note_id: r for r in results}
        # bbb should have a snippet truncated to 1000 chars
        assert "bbb" in by_id
        assert len(by_id["bbb"].snippet) == 1000
        assert by_id["bbb"].snippet == long_content[:1000]

    def test_without_vault_empty_snippets(self) -> None:
        """Without vault, snippets remain empty (no regression)."""
        graph = _build_chain_graph()
        results = graph_search(graph, ["aaa"], depth=1)
        for r in results:
            assert r.snippet == ""
