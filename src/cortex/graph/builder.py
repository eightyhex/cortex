"""Graph construction helpers — build NetworkX graph from vault notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

if TYPE_CHECKING:
    from cortex.vault.parser import Note


def add_note_node(graph: nx.MultiDiGraph, note: Note) -> None:
    """Add a note node to the graph with standard attributes."""
    graph.add_node(
        note.id,
        node_type="note",
        title=note.title,
        note_type=note.note_type,
        path=str(note.path),
    )


def add_edges_for_note(graph: nx.MultiDiGraph, note: Note) -> None:
    """Add all edges originating from a note (LINKS_TO, BELONGS_TO_PROJECT, SUPERSEDES)."""
    # LINKS_TO edges from wikilinks
    for link in note.links:
        if link.link_type == "wikilink" and graph.has_node(link.target_id):
            graph.add_edge(note.id, link.target_id, rel_type="LINKS_TO")

    # BELONGS_TO_PROJECT from frontmatter
    project = note.frontmatter.get("project")
    if project:
        project_node_id = f"project-{project}"
        if not graph.has_node(project_node_id):
            graph.add_node(project_node_id, node_type="project", title=project)
        graph.add_edge(note.id, project_node_id, rel_type="BELONGS_TO_PROJECT")

    # SUPERSEDES edge
    if note.supersedes and graph.has_node(note.supersedes):
        graph.add_edge(note.id, note.supersedes, rel_type="SUPERSEDES")


def build_graph(notes: list[Note]) -> nx.MultiDiGraph:
    """Build a complete graph from a list of notes.

    Two-pass: first add all nodes, then add edges (so targets exist).
    """
    graph = nx.MultiDiGraph()

    # Pass 1: add all note nodes
    for note in notes:
        add_note_node(graph, note)

    # Pass 2: add edges (targets now exist)
    for note in notes:
        add_edges_for_note(graph, note)

    return graph
