"""Tests for the IndexManager orchestrator."""

from datetime import datetime
from pathlib import Path

import pytest

from cortex.config import CortexConfig
from cortex.index.manager import IndexManager
from cortex.vault.parser import Note


def _make_note(
    note_id: str = "note-1",
    title: str = "Test Note",
    content: str = "Test content about machine learning.",
    tags: list[str] | None = None,
) -> Note:
    now = datetime.now()
    return Note(
        id=note_id,
        title=title,
        note_type="concept",
        path=Path(f"/vault/20-concepts/{title.lower().replace(' ', '-')}.md"),
        content=content,
        frontmatter={},
        created=now,
        modified=now,
        tags=tags or [],
        links=[],
        status="active",
    )


@pytest.fixture
def manager(tmp_path):
    """Create an IndexManager with a temp config."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    config = CortexConfig(vault={"path": str(vault_path)})
    mgr = IndexManager(config)
    yield mgr
    mgr.close()


class TestIndexManager:
    def test_index_and_search_lexical(self, manager):
        note = _make_note()
        manager.index_note(note)

        results = manager.lexical.search("machine learning")
        assert len(results) > 0
        assert results[0].note_id == "note-1"

    def test_index_and_search_semantic(self, manager):
        note = _make_note()
        manager.index_note(note)

        results = manager.semantic.search("machine learning")
        assert len(results) > 0
        assert results[0].note_id == "note-1"

    def test_remove_note_from_both(self, manager):
        note = _make_note()
        manager.index_note(note)
        manager.remove_note("note-1")

        assert len(manager.lexical.search("machine learning")) == 0
        assert len(manager.semantic.search("machine learning")) == 0

    def test_reindex_note_updates_both(self, manager):
        note = _make_note(content="Old content about Redis caching")
        manager.index_note(note)

        updated = _make_note(content="New content about PostgreSQL databases")
        manager.reindex_note(updated)

        # Old content gone from lexical
        assert len(manager.lexical.search("Redis")) == 0
        # New content in lexical
        new_lex = manager.lexical.search("PostgreSQL")
        assert len(new_lex) == 1
        assert new_lex[0].note_id == "note-1"

        # Semantic also updated — new content should be findable
        new_sem = manager.semantic.search("PostgreSQL databases")
        assert len(new_sem) > 0
        assert new_sem[0].note_id == "note-1"

    def test_rebuild_all_updates_both(self, manager):
        # Add initial note
        manager.index_note(_make_note(note_id="old-1"))

        # Rebuild with different notes
        new_notes = [
            _make_note(note_id="new-1", title="First", content="Content about databases"),
            _make_note(note_id="new-2", title="Second", content="Content about networking"),
        ]
        manager.rebuild_all(new_notes)

        # Old note gone from lexical
        assert len(manager.lexical.search("machine learning")) == 0
        # New notes in lexical
        assert len(manager.lexical.search("databases")) == 1

        # Semantic also rebuilt
        sem_results = manager.semantic.search("databases")
        assert len(sem_results) > 0
        assert sem_results[0].note_id == "new-1"

    def test_semantic_property_exposed(self, manager):
        """IndexManager exposes semantic index via property."""
        assert manager.semantic is not None
