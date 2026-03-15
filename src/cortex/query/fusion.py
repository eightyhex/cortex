"""Reciprocal Rank Fusion (RRF) for merging ranked result lists."""

from __future__ import annotations

from dataclasses import dataclass, field

from cortex.index.lexical import SearchResult


@dataclass
class FusedResult:
    """A search result after fusion, tracking which systems contributed."""

    note_id: str
    title: str
    score: float
    snippet: str
    note_type: str
    path: str
    matched_by: list[str] = field(default_factory=list)


def reciprocal_rank_fusion(
    result_lists: list[list[SearchResult]],
    k: int = 60,
    labels: list[str] | None = None,
) -> list[FusedResult]:
    """Merge ranked lists using Reciprocal Rank Fusion.

    score(d) = sum(1 / (k + rank_i(d))) for each list i where d appears.

    Args:
        result_lists: Ranked result lists from different retrieval systems.
        k: RRF constant (default 60). Higher values reduce the impact of high ranks.
        labels: Optional names for each result list (e.g. ["lexical", "semantic"]).
            Must match len(result_lists) if provided.

    Returns:
        Fused results sorted by combined RRF score descending.
    """
    if labels is not None and len(labels) != len(result_lists):
        raise ValueError("labels must match the number of result lists")

    if labels is None:
        labels = [f"system_{i}" for i in range(len(result_lists))]

    # Accumulate scores and metadata per note_id
    fused: dict[str, FusedResult] = {}

    for list_idx, results in enumerate(result_lists):
        label = labels[list_idx]
        for rank, result in enumerate(results):
            rrf_score = 1.0 / (k + rank + 1)  # rank is 0-based, formula uses 1-based

            if result.note_id in fused:
                fused[result.note_id].score += rrf_score
                if label not in fused[result.note_id].matched_by:
                    fused[result.note_id].matched_by.append(label)
            else:
                fused[result.note_id] = FusedResult(
                    note_id=result.note_id,
                    title=result.title,
                    score=rrf_score,
                    snippet=result.snippet,
                    note_type=result.note_type,
                    path=result.path,
                    matched_by=[label],
                )

    # Sort by fused score descending
    return sorted(fused.values(), key=lambda r: r.score, reverse=True)
