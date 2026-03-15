"""Heuristic-based reranker for post-fusion result adjustment."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from cortex.config import RerankerConfig
from cortex.query.pipeline import RankedResult

if TYPE_CHECKING:
    from cortex.graph.manager import GraphManager
    from cortex.index.lexical import LexicalIndex
    from cortex.index.semantic import SemanticIndex

# Note type priority: higher value = more authoritative
TYPE_PRIORITY: dict[str, float] = {
    "permanent": 1.0,
    "concept": 0.8,
    "source": 0.6,
    "project": 0.5,
    "review": 0.4,
    "task": 0.3,
    "daily": 0.2,
    "inbox": 0.1,
}

# Status boost: active notes get full boost, others penalized
STATUS_BOOST: dict[str, float] = {
    "active": 1.0,
    "draft": 0.5,
    "archived": 0.0,
    "superseded": 0.0,
}


class HeuristicReranker:
    """Reranks search results using heuristic signals: recency, type, links, status."""

    def __init__(
        self,
        config: RerankerConfig,
        lexical: LexicalIndex,
        semantic: SemanticIndex | None = None,
    ) -> None:
        self._config = config
        self._lexical = lexical
        self._semantic = semantic

    def rerank(
        self,
        results: list[RankedResult],
        query: str,
        graph: GraphManager | None = None,
    ) -> list[RankedResult]:
        """Apply heuristic boosts and return re-sorted results.

        Each result's score is adjusted:
            final_score = original_score + sum(weight_i * signal_i)

        Signals are normalized to [0, 1] before weighting.

        Args:
            results: Fused/ranked results from the pipeline.
            query: The original query string (reserved for future query-aware boosts).
            graph: Optional graph manager for link density lookups.

        Returns:
            New list of RankedResult sorted by adjusted score, with explanations.
        """
        if not results:
            return []

        # Fetch metadata for all result note_ids from the lexical index
        note_ids = [r.note_id for r in results]
        metadata = self._fetch_metadata(note_ids)

        # Compute inbound link counts from graph
        inbound_counts: dict[str, int] = {}
        if graph is not None:
            inbound_counts = self._count_inbound_links(graph, note_ids)

        # Normalize link counts for scoring
        max_links = max(inbound_counts.values()) if inbound_counts else 0

        now = datetime.now(timezone.utc)
        reranked: list[RankedResult] = []

        for result in results:
            boosts: list[str] = []
            boost_total = 0.0
            meta = metadata.get(result.note_id, {})

            # 1. Recency boost
            created = meta.get("created")
            if created and self._config.recency_weight > 0:
                age_days = max((now - created).days, 0)
                halflife = self._config.recency_halflife_days
                recency_signal = math.exp(-0.693 * age_days / halflife)  # ln(2) ≈ 0.693
                recency_boost = self._config.recency_weight * recency_signal
                boost_total += recency_boost
                if recency_signal > 0.5:
                    boosts.append(f"recency(+{recency_boost:.3f})")

            # 2. Note type priority boost
            note_type = result.note_type or meta.get("note_type", "")
            if note_type and self._config.type_weight > 0:
                type_signal = TYPE_PRIORITY.get(note_type, 0.1)
                type_boost = self._config.type_weight * type_signal
                boost_total += type_boost
                if type_signal >= 0.5:
                    boosts.append(f"type:{note_type}(+{type_boost:.3f})")

            # 3. Inbound link density boost
            link_count = inbound_counts.get(result.note_id, 0)
            if max_links > 0 and self._config.link_weight > 0:
                link_signal = link_count / max_links
                link_boost = self._config.link_weight * link_signal
                boost_total += link_boost
                if link_signal > 0:
                    boosts.append(f"links:{link_count}(+{link_boost:.3f})")

            # 4. Status boost
            status = meta.get("status", "active")
            if self._config.status_weight > 0:
                status_signal = STATUS_BOOST.get(status, 0.0)
                status_boost = self._config.status_weight * status_signal
                boost_total += status_boost
                if status_signal < 1.0:
                    boosts.append(f"status:{status}(+{status_boost:.3f})")

            new_score = result.score + boost_total
            reranked.append(replace(result, score=new_score))

        # Sort by adjusted score descending
        reranked.sort(key=lambda r: r.score, reverse=True)
        return reranked

    def _fetch_metadata(self, note_ids: list[str]) -> dict[str, dict]:
        """Fetch note metadata (created, note_type, status) from lexical index.

        Falls back to semantic index for notes not found in lexical index.
        """
        if not note_ids:
            return {}

        result: dict[str, dict] = {}

        # Step 1: Try lexical index
        try:
            placeholders = ", ".join("?" for _ in note_ids)
            rows = self._lexical._conn.execute(
                f"SELECT id, created, note_type, status FROM notes WHERE id IN ({placeholders})",
                note_ids,
            ).fetchall()

            for note_id, created, note_type, status in rows:
                meta: dict = {"note_type": note_type or "", "status": status or "active"}
                if created is not None:
                    if isinstance(created, datetime):
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)
                        meta["created"] = created
                    else:
                        # Handle string dates
                        try:
                            meta["created"] = datetime.fromisoformat(str(created)).replace(
                                tzinfo=timezone.utc
                            )
                        except (ValueError, TypeError):
                            pass
                result[note_id] = meta
        except Exception:
            pass

        # Step 2: Fall back to semantic index for missing notes
        missing = [nid for nid in note_ids if nid not in result]
        if missing and self._semantic is not None:
            result.update(self._fetch_semantic_metadata(missing))

        return result

    def _fetch_semantic_metadata(self, note_ids: list[str]) -> dict[str, dict]:
        """Fetch metadata from the semantic index for notes not in the lexical index."""
        result: dict[str, dict] = {}
        try:
            table = self._semantic._get_table()
            for note_id in note_ids:
                rows = table.search().where(f"note_id = '{note_id}'").limit(1).to_list()
                if not rows:
                    continue
                row = rows[0]
                meta: dict = {
                    "note_type": row.get("note_type", ""),
                    "status": row.get("status", "") or "active",
                }
                created_str = row.get("created", "")
                if created_str:
                    try:
                        meta["created"] = datetime.fromisoformat(str(created_str)).replace(
                            tzinfo=timezone.utc
                        )
                    except (ValueError, TypeError):
                        pass
                result[note_id] = meta
        except Exception:
            pass
        return result

    def _count_inbound_links(
        self, graph: GraphManager, note_ids: list[str]
    ) -> dict[str, int]:
        """Count inbound edges for each note in the graph."""
        counts: dict[str, int] = {}
        g = graph.graph
        for note_id in note_ids:
            if g.has_node(note_id):
                counts[note_id] = g.in_degree(note_id)
            else:
                counts[note_id] = 0
        return counts
