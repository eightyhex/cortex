"""
Retrieval Quality Metrics

MRR@k, Precision@k, NDCG@k for evaluating retrieval quality.

See docs/02-ARCHITECTURE.md § 8a for metric definitions and targets.
"""

from __future__ import annotations

import math


def mrr_at_k(results: list[str], relevant: list[str], k: int = 10) -> float:
    """Mean Reciprocal Rank at k.

    Returns 1/rank of the first relevant result in the top-k,
    or 0.0 if no relevant result appears.
    """
    relevant_set = set(relevant)
    for i, result in enumerate(results[:k]):
        if result in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def precision_at_k(results: list[str], relevant: list[str], k: int = 5) -> float:
    """Precision at k.

    Returns the fraction of top-k results that are relevant,
    or 0.0 if k is 0 or results are empty.
    """
    if k <= 0:
        return 0.0
    relevant_set = set(relevant)
    top_k = results[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for r in top_k if r in relevant_set)
    return hits / k


def ndcg_at_k(results: list[str], relevant: list[str], k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain at k.

    Uses binary relevance: 1 if the result is in the relevant set, 0 otherwise.
    Returns 0.0 if there are no relevant results or results are empty.
    """
    relevant_set = set(relevant)
    top_k = results[:k]

    # DCG: sum of rel_i / log2(i + 2) for i in 0..k-1
    dcg = 0.0
    for i, result in enumerate(top_k):
        if result in relevant_set:
            dcg += 1.0 / math.log2(i + 2)

    if dcg == 0.0:
        return 0.0

    # Ideal DCG: all relevant docs at the top
    ideal_count = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))

    return dcg / idcg
