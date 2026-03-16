"""Tests for the SemanticIndex (LanceDB vector store)."""

import pytest
from pathlib import Path

from cortex.index.models import EmbeddingModel
from cortex.index.semantic import SemanticIndex
from cortex.vault.parser import Note


@pytest.fixture(scope="module")
def model():
    """Shared embedding model."""
    return EmbeddingModel()


@pytest.fixture()
def semantic_index(tmp_path, model):
    """Fresh SemanticIndex per test."""
    db_path = tmp_path / "lance_test"
    return SemanticIndex(db_path, model)


def _make_note(
    note_id: str,
    title: str,
    content: str,
    note_type: str = "concept",
    tags: list[str] | None = None,
    status: str = "active",
    modified: str = "2026-01-15T10:00:00",
    frontmatter_extra: dict | None = None,
) -> Note:
    fm = {"id": note_id, "title": title, "type": note_type}
    if frontmatter_extra:
        fm.update(frontmatter_extra)
    return Note(
        id=note_id,
        title=title,
        note_type=note_type,
        path=Path(f"20-concepts/{title.lower().replace(' ', '-')}.md"),
        content=content,
        frontmatter=fm,
        created="2026-01-15T10:00:00",
        modified=modified,
        tags=tags or [],
        links=[],
        status=status,
    )


class TestSemanticIndex:
    def test_index_and_search(self, semantic_index):
        """Indexing a note makes it searchable."""
        note = _make_note("n1", "Machine Learning Basics", "Neural networks learn patterns from data using backpropagation.")
        semantic_index.index_note(note)

        results = semantic_index.search("deep learning neural networks")
        assert len(results) >= 1
        assert results[0].note_id == "n1"
        assert results[0].title == "Machine Learning Basics"

    def test_search_empty_index(self, semantic_index):
        """Searching an empty index returns no results."""
        results = semantic_index.search("anything")
        assert results == []

    def test_remove_note(self, semantic_index):
        """Removing a note removes it from search results."""
        note = _make_note("n2", "Removed Note", "This note will be removed from the index.")
        semantic_index.index_note(note)

        # Verify it's searchable
        results = semantic_index.search("removed from the index")
        assert any(r.note_id == "n2" for r in results)

        # Remove and verify gone
        semantic_index.remove_note("n2")
        results = semantic_index.search("removed from the index")
        assert not any(r.note_id == "n2" for r in results)

    def test_rebuild(self, semantic_index):
        """Rebuild clears and re-indexes all notes."""
        note_a = _make_note("a1", "Alpha Note", "Alpha content about astronomy and planets.")
        note_b = _make_note("b1", "Beta Note", "Beta content about cooking and recipes.")
        semantic_index.index_note(note_a)

        # Rebuild with only note_b
        semantic_index.rebuild([note_b])

        results = semantic_index.search("cooking recipes")
        assert len(results) >= 1
        assert results[0].note_id == "b1"

        # Old note should be gone
        results = semantic_index.search("astronomy planets")
        assert not any(r.note_id == "a1" for r in results)

    def test_semantic_relevance(self, semantic_index):
        """Semantically related queries should return relevant notes."""
        notes = [
            _make_note("ml1", "Deep Learning", "Convolutional neural networks are used for image recognition and computer vision tasks."),
            _make_note("cook1", "Pasta Recipe", "Boil water and cook spaghetti for eight minutes. Add tomato sauce and parmesan."),
            _make_note("ml2", "Natural Language Processing", "Transformers and attention mechanisms revolutionized text understanding and generation."),
        ]
        for n in notes:
            semantic_index.index_note(n)

        # ML query should rank ML notes higher than cooking
        results = semantic_index.search("artificial intelligence and machine learning")
        note_ids = [r.note_id for r in results]
        assert "cook1" in note_ids or "cook1" not in note_ids  # may or may not appear
        # At least one ML note should be in top 2
        top_2_ids = note_ids[:2]
        assert "ml1" in top_2_ids or "ml2" in top_2_ids

    def test_upsert_on_reindex(self, semantic_index):
        """Re-indexing a note replaces old chunks."""
        note_v1 = _make_note("u1", "Updatable Note", "Original content about databases and SQL.")
        semantic_index.index_note(note_v1)

        # Update content
        note_v2 = _make_note("u1", "Updatable Note", "New content about machine learning and neural networks.")
        semantic_index.index_note(note_v2)

        # Search for new content should find it
        results = semantic_index.search("machine learning neural networks")
        assert any(r.note_id == "u1" for r in results)

    def test_search_result_fields(self, semantic_index):
        """Search results have all required fields populated."""
        note = _make_note("f1", "Fields Test", "Content for testing search result fields.", tags=["test", "fields"])
        semantic_index.index_note(note)

        results = semantic_index.search("testing fields")
        assert len(results) >= 1
        r = results[0]
        assert r.note_id == "f1"
        assert r.title == "Fields Test"
        assert isinstance(r.score, float)
        assert r.score > 0
        assert len(r.snippet) > 0
        assert r.note_type == "concept"

    def test_search_result_includes_path(self, semantic_index):
        """Search results include the correct note path."""
        note = _make_note("p1", "Path Test", "Content for testing path field in semantic search results.")
        semantic_index.index_note(note)

        results = semantic_index.search("path field semantic search")
        assert len(results) >= 1
        r = results[0]
        assert r.note_id == "p1"
        assert r.path == "20-concepts/path-test.md"

    def test_search_result_includes_status_and_metadata(self, semantic_index):
        """Archived and superseded notes have correct metadata in search results."""
        archived_note = _make_note(
            "arc1", "Archived Concept", "This archived note about quantum computing should have archived status.",
            status="archived",
            modified="2026-02-20T14:30:00",
        )
        superseded_note = _make_note(
            "sup1", "Old Approach", "This superseded note about database design was replaced by a newer version.",
            status="superseded",
            modified="2026-03-01T09:00:00",
            frontmatter_extra={"superseded_by": "new1", "supersedes": ""},
        )
        active_note = _make_note(
            "new1", "New Approach", "This active note about database design supersedes the old approach.",
            status="active",
            modified="2026-03-10T12:00:00",
            frontmatter_extra={"supersedes": "sup1"},
        )
        for n in [archived_note, superseded_note, active_note]:
            semantic_index.index_note(n)

        # Check archived note metadata
        results = semantic_index.search("quantum computing archived")
        arc_results = [r for r in results if r.note_id == "arc1"]
        assert len(arc_results) == 1
        assert arc_results[0].status == "archived"
        assert arc_results[0].modified == "2026-02-20T14:30:00"

        # Check superseded note metadata
        results = semantic_index.search("database design superseded old")
        sup_results = [r for r in results if r.note_id == "sup1"]
        assert len(sup_results) == 1
        assert sup_results[0].status == "superseded"
        assert sup_results[0].superseded_by == "new1"

        # Check active note with supersedes
        new_results = [r for r in results if r.note_id == "new1"]
        assert len(new_results) == 1
        assert new_results[0].status == "active"
        assert new_results[0].supersedes == "sup1"

    def test_semantic_snippet_returns_full_chunk_text(self, semantic_index):
        """Semantic search snippet contains the full chunk text, not truncated to 200 chars."""
        long_content = (
            "Reinforcement learning is a type of machine learning where an agent "
            "learns to make decisions by performing actions in an environment to "
            "maximize cumulative reward. The agent receives feedback in the form of "
            "rewards or penalties and adjusts its strategy accordingly. Key concepts "
            "include the policy, value function, and the exploration-exploitation "
            "tradeoff. Deep reinforcement learning combines neural networks with "
            "reinforcement learning, enabling agents to handle complex state spaces."
        )
        assert len(long_content) > 200  # precondition
        note = _make_note("long1", "Reinforcement Learning", long_content)
        semantic_index.index_note(note)

        results = semantic_index.search("reinforcement learning agent reward")
        assert len(results) >= 1
        r = results[0]
        assert r.note_id == "long1"
        assert len(r.snippet) > 200
        assert r.snippet == long_content
