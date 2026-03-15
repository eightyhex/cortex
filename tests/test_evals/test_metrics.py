"""Tests for retrieval quality metrics."""

from __future__ import annotations

import math

from evals.metrics import mrr_at_k, ndcg_at_k, precision_at_k


class TestMrrAtK:
    def test_perfect_ranking(self):
        """First result is relevant → MRR = 1.0."""
        assert mrr_at_k(["a", "b", "c"], ["a"], k=10) == 1.0

    def test_relevant_at_position_3(self):
        """First relevant result at rank 3 → MRR = 1/3."""
        assert mrr_at_k(["x", "y", "a"], ["a"], k=10) == pytest.approx(1 / 3)

    def test_no_match(self):
        """No relevant results → MRR = 0.0."""
        assert mrr_at_k(["x", "y", "z"], ["a", "b"], k=10) == 0.0

    def test_relevant_beyond_k(self):
        """Relevant result exists but beyond k → MRR = 0.0."""
        assert mrr_at_k(["x", "y", "a"], ["a"], k=2) == 0.0

    def test_empty_results(self):
        assert mrr_at_k([], ["a"], k=10) == 0.0

    def test_empty_relevant(self):
        assert mrr_at_k(["a", "b"], [], k=10) == 0.0


class TestPrecisionAtK:
    def test_perfect_precision(self):
        """All top-k are relevant → precision = 1.0."""
        assert precision_at_k(["a", "b", "c"], ["a", "b", "c"], k=3) == 1.0

    def test_partial_match(self):
        """2 out of 5 relevant → precision = 0.4."""
        assert precision_at_k(["a", "x", "b", "y", "z"], ["a", "b"], k=5) == pytest.approx(0.4)

    def test_no_match(self):
        assert precision_at_k(["x", "y", "z"], ["a", "b"], k=3) == 0.0

    def test_k_larger_than_results(self):
        """k=5 but only 2 results, 1 relevant → 1/5 = 0.2."""
        assert precision_at_k(["a", "x"], ["a"], k=5) == pytest.approx(0.2)

    def test_empty_results(self):
        assert precision_at_k([], ["a"], k=5) == 0.0


class TestNdcgAtK:
    def test_perfect_ranking(self):
        """All relevant at top → NDCG = 1.0."""
        assert ndcg_at_k(["a", "b", "c"], ["a", "b"], k=10) == pytest.approx(1.0)

    def test_inverted_ranking(self):
        """Relevant docs at bottom — should be < 1.0."""
        score = ndcg_at_k(["x", "y", "a", "b"], ["a", "b"], k=10)
        assert 0.0 < score < 1.0

    def test_no_match(self):
        assert ndcg_at_k(["x", "y", "z"], ["a", "b"], k=10) == 0.0

    def test_single_relevant_at_top(self):
        """One relevant doc at rank 1 → NDCG = 1.0."""
        assert ndcg_at_k(["a", "x", "y"], ["a"], k=10) == pytest.approx(1.0)

    def test_single_relevant_at_rank_2(self):
        """One relevant at rank 2: DCG = 1/log2(3), IDCG = 1/log2(2) → NDCG < 1."""
        score = ndcg_at_k(["x", "a"], ["a"], k=10)
        expected = (1.0 / math.log2(3)) / (1.0 / math.log2(2))
        assert score == pytest.approx(expected)

    def test_empty_results(self):
        assert ndcg_at_k([], ["a"], k=10) == 0.0

    def test_empty_relevant(self):
        assert ndcg_at_k(["a", "b"], [], k=10) == 0.0


import pytest
