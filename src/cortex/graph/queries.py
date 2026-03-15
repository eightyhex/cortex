"""Graph query patterns for knowledge graph retrieval."""

from __future__ import annotations

import networkx as nx

from cortex.index.lexical import SearchResult


def get_neighbors(graph: nx.MultiDiGraph, note_id: str, depth: int = 1) -> list[str]:
    """Return BFS neighbors up to *depth* hops from *note_id*.

    Returns node IDs reachable within the given depth (excludes the start node).
    Uses the undirected view so both incoming and outgoing edges are traversed.
    """
    if not graph.has_node(note_id):
        return []

    undirected = graph.to_undirected(as_view=True)
    visited: list[str] = []
    for _src, dst in nx.bfs_edges(undirected, note_id, depth_limit=depth):
        if dst != note_id:
            visited.append(dst)
    return visited


def find_path(graph: nx.MultiDiGraph, source_id: str, target_id: str) -> list[str]:
    """Return the shortest path between two nodes (as list of node IDs).

    Works on the undirected view so direction doesn't block traversal.
    Returns an empty list if no path exists or either node is missing.
    """
    if not graph.has_node(source_id) or not graph.has_node(target_id):
        return []

    undirected = graph.to_undirected(as_view=True)
    try:
        return list(nx.shortest_path(undirected, source_id, target_id))
    except nx.NetworkXNoPath:
        return []


def get_cluster(graph: nx.MultiDiGraph, note_id: str, max_nodes: int = 20) -> list[str]:
    """Return the ego graph (local cluster) around *note_id*.

    Uses `nx.ego_graph` on the undirected view, increasing radius until
    *max_nodes* is reached or the full connected component is captured.
    Returns node IDs excluding the center node.
    """
    if not graph.has_node(note_id):
        return []

    undirected = graph.to_undirected(as_view=True)
    # Start with radius 1 and expand
    radius = 1
    while True:
        ego = nx.ego_graph(undirected, note_id, radius=radius)
        nodes = [n for n in ego.nodes() if n != note_id]
        if len(nodes) >= max_nodes:
            return nodes[:max_nodes]
        # Check if we've reached the full component
        next_ego = nx.ego_graph(undirected, note_id, radius=radius + 1)
        if next_ego.number_of_nodes() == ego.number_of_nodes():
            # No more nodes to discover
            return nodes[:max_nodes]
        radius += 1


def get_project_notes(graph: nx.MultiDiGraph, project_id: str) -> list[str]:
    """Return all note IDs linked to a project node via BELONGS_TO_PROJECT."""
    if not graph.has_node(project_id):
        return []

    note_ids: list[str] = []
    # Notes have outgoing BELONGS_TO_PROJECT edges to the project node
    for src, _dst, data in graph.in_edges(project_id, data=True):
        if data.get("rel_type") == "BELONGS_TO_PROJECT":
            note_ids.append(src)
    return note_ids


def graph_search(
    graph: nx.MultiDiGraph,
    note_ids: list[str],
    depth: int = 1,
) -> list[SearchResult]:
    """Expand seed note IDs via graph and return neighbor notes as SearchResults.

    Given seed note IDs (from lexical/semantic search), find graph neighbors
    up to *depth* hops. Returns SearchResult objects for neighbor notes that
    are NOT already in the seed set. Score decays by depth (1.0 / hop_distance).
    """
    seeds = set(note_ids)
    results: dict[str, SearchResult] = {}

    for seed_id in note_ids:
        if not graph.has_node(seed_id):
            continue

        undirected = graph.to_undirected(as_view=True)
        # BFS with depth tracking
        for src, dst in nx.bfs_edges(undirected, seed_id, depth_limit=depth):
            if dst in seeds or dst in results:
                continue
            # Skip non-note nodes (e.g., project nodes)
            node_data = graph.nodes.get(dst, {})
            if node_data.get("node_type") != "note":
                continue

            # Calculate hop distance from seed
            try:
                hop = nx.shortest_path_length(undirected, seed_id, dst)
            except nx.NetworkXNoPath:
                hop = depth
            score = 1.0 / hop if hop > 0 else 1.0

            results[dst] = SearchResult(
                note_id=dst,
                title=node_data.get("title", ""),
                score=score,
                snippet="",
                note_type=node_data.get("note_type", ""),
                path=node_data.get("path", ""),
            )

    return list(results.values())
