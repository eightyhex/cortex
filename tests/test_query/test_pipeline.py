"""Tests for QueryPipeline — end-to-end hybrid search."""

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from cortex.config import CortexConfig
from cortex.graph.manager import GraphManager
from cortex.index.lexical import LexicalIndex
from cortex.index.models import EmbeddingModel
from cortex.index.semantic import SemanticIndex
from cortex.query.pipeline import QueryPipeline, STATUS_MULTIPLIERS
from cortex.vault.parser import Link, Note


def _make_note(
    note_id: str,
    title: str,
    content: str,
    note_type: str = "concept",
    status: str = "active",
    tags: list[str] | None = None,
) -> Note:
    return Note(
        id=note_id,
        title=title,
        note_type=note_type,
        path=Path(f"20-concepts/{note_id}.md"),
        content=content,
        frontmatter={"status": status},
        created=datetime(2026, 1, 1),
        modified=datetime(2026, 1, 1),
        tags=tags or [],
        links=[],
        status=status,
    )


@pytest.fixture
def tmp_indexes(tmp_path):
    """Create real lexical + semantic indexes in a temp dir."""
    lexical = LexicalIndex(tmp_path / "lexical.duckdb")
    model = EmbeddingModel()
    semantic = SemanticIndex(tmp_path / "semantic.lancedb", model)
    return lexical, semantic


@pytest.fixture
def sample_notes():
    """Sample notes for indexing."""
    return [
        _make_note(
            "note-ml",
            "Machine Learning Basics",
            "Machine learning is a subset of artificial intelligence that enables systems to learn from data. "
            "Neural networks and deep learning are key techniques in modern ML.",
        ),
        _make_note(
            "note-py",
            "Python Programming Guide",
            "Python is a versatile programming language used for web development, data science, and automation. "
            "It has a rich ecosystem of libraries like NumPy, pandas, and scikit-learn.",
        ),
        _make_note(
            "note-cook",
            "Italian Cooking Techniques",
            "Italian cuisine emphasizes fresh ingredients, simple preparations, and regional traditions. "
            "Pasta, olive oil, and tomatoes are staple ingredients.",
        ),
    ]


class TestQueryPipeline:
    """Tests for the QueryPipeline class."""

    def test_end_to_end_query(self, tmp_indexes, sample_notes):
        """Full pipeline: index notes, query, get results with context."""
        lexical, semantic = tmp_indexes
        for note in sample_notes:
            lexical.index_note(note)
            semantic.index_note(note)

        pipeline = QueryPipeline(lexical, semantic)
        result = asyncio.run(pipeline.execute("machine learning", limit=10))

        assert result.query == "machine learning"
        assert len(result.results) > 0
        # ML note should rank highest
        assert result.results[0].note_id == "note-ml"
        # Context should be non-empty
        assert "machine learning" in result.context.lower() or "Machine" in result.context
        # Explanation should mention source systems
        assert "lexical" in result.explanation or "semantic" in result.explanation

    def test_status_multipliers_applied(self, tmp_indexes):
        """Archived/superseded notes get score penalties."""
        lexical, semantic = tmp_indexes

        active_note = _make_note(
            "active-1", "Active Machine Learning", "Machine learning concepts and techniques", status="active"
        )
        archived_note = _make_note(
            "archived-1", "Archived Machine Learning", "Machine learning old techniques", status="archived"
        )

        for note in [active_note, archived_note]:
            lexical.index_note(note)
            semantic.index_note(note)

        pipeline = QueryPipeline(lexical, semantic)
        result = asyncio.run(pipeline.execute("machine learning", limit=10))

        results_by_id = {r.note_id: r for r in result.results}

        # Both should appear
        assert "active-1" in results_by_id
        assert "archived-1" in results_by_id

        # Active should score higher than archived (archived gets 0.3 multiplier)
        assert results_by_id["active-1"].score > results_by_id["archived-1"].score

    def test_explanation_includes_source_systems(self, tmp_indexes, sample_notes):
        """Explanation field mentions which retrieval systems contributed."""
        lexical, semantic = tmp_indexes
        for note in sample_notes:
            lexical.index_note(note)
            semantic.index_note(note)

        pipeline = QueryPipeline(lexical, semantic)
        result = asyncio.run(pipeline.execute("python programming"))

        assert "Search via" in result.explanation
        # At least one system should be mentioned
        assert "lexical" in result.explanation or "semantic" in result.explanation

    def test_empty_results(self, tmp_indexes):
        """Query with no matches returns empty results."""
        lexical, semantic = tmp_indexes
        pipeline = QueryPipeline(lexical, semantic)
        result = asyncio.run(pipeline.execute("xyznonexistent"))

        assert result.query == "xyznonexistent"
        assert len(result.results) == 0
        assert "0 results" in result.context or "No results" in result.context

    def test_limit_respected(self, tmp_indexes):
        """Results are limited to the requested count."""
        lexical, semantic = tmp_indexes

        # Index many notes about the same topic
        notes = [
            _make_note(
                f"note-{i}",
                f"Machine Learning Part {i}",
                f"Machine learning concepts part {i} with neural networks and deep learning.",
            )
            for i in range(10)
        ]
        for note in notes:
            lexical.index_note(note)
            semantic.index_note(note)

        pipeline = QueryPipeline(lexical, semantic)
        result = asyncio.run(pipeline.execute("machine learning", limit=3))

        assert len(result.results) <= 3

    def test_ranked_result_fields(self, tmp_indexes, sample_notes):
        """RankedResult has all expected fields populated."""
        lexical, semantic = tmp_indexes
        for note in sample_notes:
            lexical.index_note(note)
            semantic.index_note(note)

        pipeline = QueryPipeline(lexical, semantic)
        result = asyncio.run(pipeline.execute("python"))

        for r in result.results:
            assert r.note_id
            assert r.title
            assert r.score > 0
            assert isinstance(r.matched_by, list)
            assert len(r.matched_by) > 0

    def test_graph_integration(self, tmp_indexes, tmp_path):
        """Graph search contributes neighbors to fused results."""
        lexical, semantic = tmp_indexes

        # Note A (indexed) links to Note B (not indexed in lexical/semantic)
        note_a = _make_note(
            "note-a",
            "Neural Networks Overview",
            "Neural networks are computational models inspired by the brain.",
            tags=["ml"],
        )
        note_a = Note(
            id=note_a.id,
            title=note_a.title,
            note_type=note_a.note_type,
            path=note_a.path,
            content=note_a.content,
            frontmatter=note_a.frontmatter,
            created=note_a.created,
            modified=note_a.modified,
            tags=note_a.tags,
            links=[
                Link(source_id="note-a", target_id="note-b", target_title="Deep Learning", link_type="wikilink"),
            ],
            status=note_a.status,
        )
        note_b = _make_note(
            "note-b",
            "Deep Learning",
            "Deep learning uses multiple layers of neural networks.",
            tags=["ml"],
        )

        # Only index note_a in lexical/semantic — note_b is only reachable via graph
        lexical.index_note(note_a)
        semantic.index_note(note_a)

        # Build graph with both notes
        graph_manager = GraphManager(tmp_path / "graph.graphml")
        graph_manager.build_from_vault([note_a, note_b])

        pipeline = QueryPipeline(lexical, semantic, graph=graph_manager)
        result = asyncio.run(pipeline.execute("neural networks", limit=10))

        # note_a should appear (from lexical/semantic)
        result_ids = [r.note_id for r in result.results]
        assert "note-a" in result_ids

        # note_b should appear via graph expansion
        assert "note-b" in result_ids

        # Explanation should mention graph
        assert "graph" in result.explanation

        # note_b should have "graph" in matched_by
        note_b_result = next(r for r in result.results if r.note_id == "note-b")
        assert "graph" in note_b_result.matched_by
