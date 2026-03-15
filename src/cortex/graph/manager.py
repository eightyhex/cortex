"""GraphManager — knowledge graph lifecycle with NetworkX and GraphML persistence."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import networkx as nx

from cortex.graph.builder import add_edges_for_note, add_note_node, build_graph

if TYPE_CHECKING:
    from cortex.vault.parser import Note


class GraphManager:
    """Manages the knowledge graph: build, update, persist via GraphML."""

    def __init__(self, graph_path: Path) -> None:
        """Load graph from GraphML file, or create an empty MultiDiGraph."""
        self._path = graph_path
        if graph_path.exists():
            self._graph = nx.read_graphml(graph_path)
            # Ensure it's a MultiDiGraph (GraphML may deserialize as generic)
            if not isinstance(self._graph, nx.MultiDiGraph):
                self._graph = nx.MultiDiGraph(self._graph)
        else:
            self._graph = nx.MultiDiGraph()

    @property
    def graph(self) -> nx.MultiDiGraph:
        """Expose the underlying NetworkX graph."""
        return self._graph

    def save(self) -> None:
        """Write graph to GraphML with backup."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            shutil.copy2(self._path, self._path.with_suffix(".graphml.bak"))
        nx.write_graphml(self._graph, str(self._path))

    def build_from_vault(self, notes: list[Note]) -> None:
        """Clear graph and rebuild from all vault notes."""
        self._graph = build_graph(notes)

    def update_note(self, note: Note) -> None:
        """Update or add a single note node and re-create its edges."""
        # Remove existing edges originating from this node
        if self._graph.has_node(note.id):
            edges_to_remove = list(self._graph.out_edges(note.id, keys=True))
            self._graph.remove_edges_from(edges_to_remove)

        # Add/update the node
        add_note_node(self._graph, note)

        # Re-add edges
        add_edges_for_note(self._graph, note)

    def remove_note(self, note_id: str) -> None:
        """Remove a node and all connected edges."""
        if self._graph.has_node(note_id):
            self._graph.remove_node(note_id)
