"""QueryPipeline — orchestrates multi-stage retrieval: search → fusion → rerank → context assembly."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cortex.config import RerankerConfig
from cortex.index.lexical import LexicalIndex, SearchResult
from cortex.index.semantic import SemanticIndex
from cortex.query.context import ContextAssembler
from cortex.query.fusion import FusedResult, reciprocal_rank_fusion

if TYPE_CHECKING:
    from cortex.graph.manager import GraphManager
    from cortex.vault.manager import VaultManager



@dataclass
class RankedResult:
    """A final ranked result after fusion and status adjustment."""

    note_id: str
    title: str
    score: float
    matched_by: list[str] = field(default_factory=list)
    snippet: str = ""
    note_type: str = ""
    tags: list[str] = field(default_factory=list)


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
        reranker_config: RerankerConfig | None = None,
        vault: VaultManager | None = None,
    ) -> None:
        self._lexical = lexical
        self._semantic = semantic
        self._graph = graph
        self._vault = vault
        self._assembler = ContextAssembler()
        from cortex.query.reranker import HeuristicReranker

        self._reranker = HeuristicReranker(
            reranker_config or RerankerConfig(), lexical, semantic=semantic
        )

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

        # Convert to RankedResult for reranking
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

        # Apply heuristic reranker (recency, type, link density, status boosts)
        ranked = self._reranker.rerank(ranked, query, graph=self._graph)

        # Truncate to limit
        ranked = ranked[:limit]

        # Build explanation
        sources = sorted({s for r in ranked for s in r.matched_by})
        explanation = f"Search via {', '.join(sources)}. {len(ranked)} results after RRF fusion."

        # Assemble context (use fused results truncated to match ranked)
        ranked_ids = {r.note_id for r in ranked}
        fused_for_context = [r for r in fused if r.note_id in ranked_ids][:limit]

        # Look up full notes for metadata (tags, links, created date)
        notes = {}
        if self._vault:
            for r in fused_for_context:
                try:
                    notes[r.note_id] = self._vault.get_note(r.note_id)
                except (KeyError, FileNotFoundError):
                    pass

        # Populate tags on RankedResults from vault notes
        for r in ranked:
            note = notes.get(r.note_id)
            if note:
                r.tags = list(note.tags)

        context = self._assembler.assemble(fused_for_context, query, notes=notes)

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

            return graph_search(self._graph.graph, seed_ids, depth=depth, vault=self._vault)
        except Exception:
            return []

