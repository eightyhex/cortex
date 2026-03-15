"""Tests for Reciprocal Rank Fusion."""

from cortex.index.lexical import SearchResult
from cortex.query.fusion import FusedResult, reciprocal_rank_fusion


def _make_result(note_id: str, title: str = "", score: float = 1.0) -> SearchResult:
    return SearchResult(
        note_id=note_id,
        title=title or f"Note {note_id}",
        score=score,
        snippet=f"Snippet for {note_id}",
        note_type="concept",
        path=f"20-concepts/{note_id}.md",
    )


class TestReciprocalRankFusion:
    """Tests for the reciprocal_rank_fusion function."""

    def test_merge_two_lists(self):
        """Merging two result lists produces fused scores."""
        list_a = [_make_result("a"), _make_result("b"), _make_result("c")]
        list_b = [_make_result("b"), _make_result("d"), _make_result("a")]

        fused = reciprocal_rank_fusion(
            [list_a, list_b], k=60, labels=["lexical", "semantic"]
        )

        # All unique note_ids should appear
        ids = [r.note_id for r in fused]
        assert set(ids) == {"a", "b", "c", "d"}

        # "b" appears rank 2 in list_a and rank 1 in list_b → highest combined score
        assert fused[0].note_id == "b"

        # Results are sorted descending by score
        for i in range(len(fused) - 1):
            assert fused[i].score >= fused[i + 1].score

    def test_merge_three_lists(self):
        """Merging three result lists works correctly."""
        list_a = [_make_result("x"), _make_result("y")]
        list_b = [_make_result("y"), _make_result("z")]
        list_c = [_make_result("x"), _make_result("z"), _make_result("y")]

        fused = reciprocal_rank_fusion(
            [list_a, list_b, list_c], k=60, labels=["lex", "sem", "graph"]
        )

        ids = [r.note_id for r in fused]
        assert set(ids) == {"x", "y", "z"}

        # "y" appears in all three lists → should have highest score
        assert fused[0].note_id == "y"

    def test_deduplication_by_note_id(self):
        """Same note from different systems gets combined score, not duplicated."""
        list_a = [_make_result("same")]
        list_b = [_make_result("same")]

        fused = reciprocal_rank_fusion([list_a, list_b], k=60)

        assert len(fused) == 1
        assert fused[0].note_id == "same"
        # Score should be double what a single list would give
        single_score = 1.0 / (60 + 1)
        assert abs(fused[0].score - 2 * single_score) < 1e-10

    def test_empty_list_handling(self):
        """Empty result lists are handled gracefully."""
        fused = reciprocal_rank_fusion([], k=60)
        assert fused == []

        # One empty, one non-empty
        list_a = [_make_result("a")]
        fused = reciprocal_rank_fusion([list_a, []], k=60, labels=["lex", "sem"])
        assert len(fused) == 1
        assert fused[0].note_id == "a"

    def test_score_ordering(self):
        """Results are ordered by fused score descending."""
        # Note appearing at rank 1 in both lists should beat one at rank 3 in both
        list_a = [_make_result("top"), _make_result("x"), _make_result("bottom")]
        list_b = [_make_result("top"), _make_result("x"), _make_result("bottom")]

        fused = reciprocal_rank_fusion([list_a, list_b], k=60)

        assert fused[0].note_id == "top"
        assert fused[-1].note_id == "bottom"
        assert fused[0].score > fused[-1].score

    def test_matched_by_tracks_contributing_systems(self):
        """matched_by field tracks which retrieval systems contributed."""
        list_a = [_make_result("shared"), _make_result("only_lex")]
        list_b = [_make_result("shared"), _make_result("only_sem")]

        fused = reciprocal_rank_fusion(
            [list_a, list_b], k=60, labels=["lexical", "semantic"]
        )

        fused_dict = {r.note_id: r for r in fused}
        assert set(fused_dict["shared"].matched_by) == {"lexical", "semantic"}
        assert fused_dict["only_lex"].matched_by == ["lexical"]
        assert fused_dict["only_sem"].matched_by == ["semantic"]

    def test_labels_mismatch_raises(self):
        """Mismatched labels count raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="labels must match"):
            reciprocal_rank_fusion([[]], labels=["a", "b"])

    def test_preserves_metadata_from_first_occurrence(self):
        """Fused result preserves title, snippet, etc. from the first list it appears in."""
        result_a = SearchResult(
            note_id="n1",
            title="Title A",
            score=1.0,
            snippet="Snippet A",
            note_type="concept",
            path="path_a.md",
        )
        result_b = SearchResult(
            note_id="n1",
            title="Title B",
            score=0.5,
            snippet="Snippet B",
            note_type="source",
            path="path_b.md",
        )

        fused = reciprocal_rank_fusion([[result_a], [result_b]], k=60)
        assert len(fused) == 1
        # Metadata comes from first occurrence
        assert fused[0].title == "Title A"
        assert fused[0].snippet == "Snippet A"
