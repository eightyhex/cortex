"""Tests for the DuckDB-based lexical search index."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from cortex.index.lexical import LexicalIndex, SearchResult
from cortex.vault.parser import Note


def _make_note(
    note_id: str = "note-1",
    title: str = "Test Note",
    note_type: str = "concept",
    content: str = "This is a test note about machine learning.",
    tags: list[str] | None = None,
    status: str = "active",
    created: datetime | None = None,
    modified: datetime | None = None,
    **kwargs,
) -> Note:
    """Helper to create a Note for testing."""
    now = datetime.now()
    return Note(
        id=note_id,
        title=title,
        note_type=note_type,
        path=Path(f"/vault/{note_type}/{title.lower().replace(' ', '-')}.md"),
        content=content,
        frontmatter=kwargs.get("frontmatter", {}),
        created=created or now,
        modified=modified or now,
        tags=tags or [],
        links=[],
        status=status,
        supersedes=kwargs.get("supersedes"),
        superseded_by=kwargs.get("superseded_by"),
        archived_date=kwargs.get("archived_date"),
    )


@pytest.fixture
def index(tmp_path):
    """Create a LexicalIndex with a temporary database."""
    idx = LexicalIndex(tmp_path / "test.duckdb")
    yield idx
    idx.close()


@pytest.fixture
def populated_index(index):
    """Index with several notes pre-loaded."""
    notes = [
        _make_note(
            note_id="ml-1",
            title="Machine Learning Basics",
            content="Machine learning is a subset of artificial intelligence. Neural networks are key.",
            tags=["ml", "ai"],
            note_type="concept",
        ),
        _make_note(
            note_id="ml-2",
            title="Deep Learning Guide",
            content="Deep learning uses multiple layers of neural networks for pattern recognition.",
            tags=["ml", "deep-learning"],
            note_type="permanent",
        ),
        _make_note(
            note_id="py-1",
            title="Python Best Practices",
            content="Python is a versatile programming language. Use type hints and virtual environments.",
            tags=["python", "coding"],
            note_type="source",
        ),
        _make_note(
            note_id="task-1",
            title="Review ML Paper",
            content="Need to review the latest transformer architecture paper.",
            tags=["ml", "todo"],
            note_type="task",
            status="active",
        ),
        _make_note(
            note_id="archived-1",
            title="Old AI Notes",
            content="Some old notes about artificial intelligence and expert systems.",
            tags=["ai"],
            note_type="concept",
            status="archived",
        ),
    ]
    for note in notes:
        index.index_note(note)
    return index


class TestIndexNote:
    def test_index_single_note(self, index):
        note = _make_note()
        index.index_note(note)

        row = index._conn.execute("SELECT id, title FROM notes").fetchone()
        assert row is not None
        assert row[0] == "note-1"
        assert row[1] == "Test Note"

    def test_upsert_replaces_existing(self, index):
        note = _make_note(note_id="n1", title="Original")
        index.index_note(note)

        updated = _make_note(note_id="n1", title="Updated")
        index.index_note(updated)

        rows = index._conn.execute("SELECT id, title FROM notes").fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "Updated"

    def test_tags_stored_as_array_and_text(self, index):
        note = _make_note(tags=["python", "ml", "data-science"])
        index.index_note(note)

        row = index._conn.execute("SELECT tags, tags_text FROM notes").fetchone()
        assert row[0] == ["python", "ml", "data-science"]
        assert row[1] == "python ml data-science"


class TestRemoveNote:
    def test_remove_existing_note(self, index):
        note = _make_note(note_id="to-remove")
        index.index_note(note)
        index.remove_note("to-remove")

        row = index._conn.execute("SELECT COUNT(*) FROM notes").fetchone()
        assert row[0] == 0

    def test_remove_nonexistent_is_noop(self, index):
        # Should not raise
        index.remove_note("does-not-exist")


class TestRebuild:
    def test_rebuild_replaces_all(self, index):
        # Add a note first
        index.index_note(_make_note(note_id="old-1", title="Old"))

        # Rebuild with new set
        new_notes = [
            _make_note(note_id="new-1", title="New One"),
            _make_note(note_id="new-2", title="New Two"),
        ]
        index.rebuild(new_notes)

        rows = index._conn.execute("SELECT id FROM notes ORDER BY id").fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "new-1"
        assert rows[1][0] == "new-2"

    def test_rebuild_empty_list(self, index):
        index.index_note(_make_note())
        index.rebuild([])

        row = index._conn.execute("SELECT COUNT(*) FROM notes").fetchone()
        assert row[0] == 0


class TestSearch:
    def test_search_by_keyword(self, populated_index):
        results = populated_index.search("machine learning")
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)
        # ML notes should appear
        note_ids = [r.note_id for r in results]
        assert "ml-1" in note_ids

    def test_search_returns_ranked_results(self, populated_index):
        results = populated_index.search("neural networks")
        assert len(results) >= 2
        # Results should be sorted by score descending
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_search_with_note_type_filter(self, populated_index):
        results = populated_index.search("machine learning", filters={"note_type": "concept"})
        for r in results:
            assert r.note_type == "concept"

    def test_search_with_tag_filter(self, populated_index):
        results = populated_index.search("learning", filters={"tags": ["ml"]})
        note_ids = [r.note_id for r in results]
        # Python note shouldn't appear (no ml tag)
        assert "py-1" not in note_ids

    def test_search_with_status_filter(self, populated_index):
        results = populated_index.search("artificial intelligence", filters={"status": "archived"})
        for r in results:
            assert r.note_id == "archived-1"

    def test_search_with_date_range_filter(self, populated_index):
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        results = populated_index.search("machine learning", filters={"date_range": (yesterday, tomorrow)})
        assert len(results) > 0

    def test_search_no_results(self, populated_index):
        results = populated_index.search("xyznonexistentterm")
        assert results == []

    def test_search_respects_limit(self, populated_index):
        results = populated_index.search("learning", limit=1)
        assert len(results) <= 1

    def test_search_result_has_snippet(self, populated_index):
        results = populated_index.search("Python")
        assert len(results) > 0
        # Snippet should be non-empty for notes with content
        py_results = [r for r in results if r.note_id == "py-1"]
        assert len(py_results) == 1
        assert len(py_results[0].snippet) > 0


class TestBM25Ranking:
    def test_more_relevant_note_ranks_higher(self, index):
        """A note with the search term in both title and content should rank higher."""
        highly_relevant = _make_note(
            note_id="high",
            title="Redis Caching Strategies",
            content="Redis caching is essential for performance. Redis supports various caching patterns.",
            tags=["redis", "caching"],
        )
        somewhat_relevant = _make_note(
            note_id="low",
            title="Database Overview",
            content="Various databases exist. Some people use Redis for caching.",
            tags=["databases"],
        )
        index.index_note(highly_relevant)
        index.index_note(somewhat_relevant)

        results = index.search("Redis caching")
        assert len(results) == 2
        assert results[0].note_id == "high"
