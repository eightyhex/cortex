"""QueryPipeline — orchestrates multi-stage retrieval: search → fusion → context assembly."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cortex.index.lexical import LexicalIndex, SearchResult
from cortex.index.semantic import SemanticIndex
from cortex.query.context import ContextAssembler
from cortex.query.fusion import FusedResult, reciprocal_rank_fusion

if TYPE_CHECKING:
    from cortex.graph.manager import GraphManager


# Status-based score multipliers applied after fusion
STATUS_MULTIPLIERS: dict[str, float] = {
    "active": 1.0,
    "draft": 0.8,
    "archived": 0.3,
    "superseded": 0.2,
}


@dataclass
class RankedResult:
    """A final ranked result after fusion and status adjustment."""

    note_id: str
    title: str
    score: float
    matched_by: list[str] = field(default_factory=list)
    snippet: str = ""
    note_type: str = ""


@dataclass
class QueryResult:
    """Complete result of a query pipeline execution."""

    query: str
    results: list[RankedResult] = field(default_factory=list)
    context: str = ""
    explanation: str = ""


class QueryPipeline:
    """Orchestrates parallel search → RRF fusion → context assembly."""

    def __init__(
        self,
        lexical: LexicalIndex,
        semantic: SemanticIndex,
        graph: GraphManager | None = None,
    ) -> None:
        self._lexical = lexical
        self._semantic = semantic
        self._graph = graph
        self._assembler = ContextAssembler()

    async def execute(self, query: str, limit: int = 10) -> QueryResult:
        """Run lexical and semantic search in parallel, fuse, and assemble context.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            QueryResult with fused results, formatted context, and explanation.
        """
        # Run searches in parallel
        loop = asyncio.get_event_loop()
        lexical_task = loop.run_in_executor(
            None, self._safe_lexical_search, query, limit
        )
        semantic_task = loop.run_in_executor(
            None, self._safe_semantic_search, query, limit
        )

        lexical_results, semantic_results = await asyncio.gather(
            lexical_task, semantic_task
        )

        # Collect result lists and labels
        result_lists: list[list[SearchResult]] = [lexical_results, semantic_results]
        labels = ["lexical", "semantic"]

        # Graph expansion: use top-N note IDs from lexical+semantic as seeds
        if self._graph is not None:
            seed_ids = list(
                dict.fromkeys(
                    r.note_id
                    for r in (lexical_results + semantic_results)
                )
            )
            graph_results = self._safe_graph_search(seed_ids, depth=1)
            if graph_results:
                result_lists.append(graph_results)
                labels.append("graph")

        # Fuse via RRF
        fused = reciprocal_rank_fusion(result_lists, labels=labels)

        # Apply status-based score multipliers
        # Look up status from lexical index results for each note
        status_map = self._build_status_map(lexical_results, semantic_results)
        for result in fused:
            status = status_map.get(result.note_id, "active")
            multiplier = STATUS_MULTIPLIERS.get(status, 1.0)
            result.score *= multiplier

        # Re-sort after multiplier application
        fused.sort(key=lambda r: r.score, reverse=True)

        # Truncate to limit
        fused = fused[:limit]

        # Convert to RankedResult
        ranked = [
            RankedResult(
                note_id=r.note_id,
                title=r.title,
                score=r.score,
                matched_by=r.matched_by,
                snippet=r.snippet,
                note_type=r.note_type,
            )
            for r in fused
        ]

        # Build explanation
        sources = sorted({s for r in ranked for s in r.matched_by})
        explanation = f"Search via {', '.join(sources)}. {len(ranked)} results after RRF fusion."

        # Assemble context
        context = self._assembler.assemble(fused, query)

        return QueryResult(
            query=query,
            results=ranked,
            context=context,
            explanation=explanation,
        )

    def _safe_lexical_search(self, query: str, limit: int) -> list[SearchResult]:
        """Lexical search with graceful error handling."""
        try:
            return self._lexical.search(query, limit)
        except Exception:
            return []

    def _safe_semantic_search(self, query: str, limit: int) -> list[SearchResult]:
        """Semantic search with graceful error handling."""
        try:
            return self._semantic.search(query, limit)
        except Exception:
            return []

    def _safe_graph_search(self, seed_ids: list[str], depth: int) -> list[SearchResult]:
        """Graph search with graceful error handling."""
        try:
            from cortex.graph.queries import graph_search

            return graph_search(self._graph.graph, seed_ids, depth=depth)
        except Exception:
            return []

    def _build_status_map(self, *result_lists: list[SearchResult]) -> dict[str, str]:
        """Build a note_id -> status mapping by querying the lexical index.

        We look up status from the DuckDB notes table for each unique note_id.
        """
        all_ids = set()
        for results in result_lists:
            for r in results:
                all_ids.add(r.note_id)

        if not all_ids:
            return {}

        status_map: dict[str, str] = {}
        try:
            # Query DuckDB for status of all note_ids
            placeholders = ", ".join("?" for _ in all_ids)
            rows = self._lexical._conn.execute(
                f"SELECT id, status FROM notes WHERE id IN ({placeholders})",
                list(all_ids),
            ).fetchall()
            for note_id, status in rows:
                if status:
                    status_map[note_id] = status
        except Exception:
            pass

        return status_map
