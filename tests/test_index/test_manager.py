"""Tests for the IndexManager orchestrator."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

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
    def test_index_and_search(self, manager):
        note = _make_note()
        manager.index_note(note)

        results = manager.lexical.search("machine learning")
        assert len(results) > 0
        assert results[0].note_id == "note-1"

    def test_remove_note(self, manager):
        note = _make_note()
        manager.index_note(note)
        manager.remove_note("note-1")

        results = manager.lexical.search("machine learning")
        assert len(results) == 0

    def test_reindex_note(self, manager):
        note = _make_note(content="Old content about Redis")
        manager.index_note(note)

        updated = _make_note(content="New content about PostgreSQL")
        manager.reindex_note(updated)

        # Old content should not match
        old_results = manager.lexical.search("Redis")
        assert len(old_results) == 0

        # New content should match
        new_results = manager.lexical.search("PostgreSQL")
        assert len(new_results) == 1
        assert new_results[0].note_id == "note-1"

    def test_rebuild_all(self, manager):
        # Add initial note
        manager.index_note(_make_note(note_id="old-1"))

        # Rebuild with different notes
        new_notes = [
            _make_note(note_id="new-1", title="First", content="Content about databases"),
            _make_note(note_id="new-2", title="Second", content="Content about networking"),
        ]
        manager.rebuild_all(new_notes)

        # Old note gone
        old_results = manager.lexical.search("machine learning")
        assert len(old_results) == 0

        # New notes present
        db_results = manager.lexical.search("databases")
        assert len(db_results) == 1
        assert db_results[0].note_id == "new-1"
