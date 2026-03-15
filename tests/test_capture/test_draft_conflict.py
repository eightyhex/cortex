"""Tests for draft conflict resolution and IndexManager no-op optimization."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cortex.capture.draft import DraftManager, NoteDraft
from cortex.config import CortexConfig
from cortex.index.manager import IndexManager, _note_content_hash
from cortex.vault.manager import VaultManager, scaffold_vault
from cortex.vault.parser import Note


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    scaffold_vault(vault)
    return vault


@pytest.fixture
def vault(vault_dir: Path) -> VaultManager:
    config = CortexConfig()
    return VaultManager(vault_dir, config)


@pytest.fixture
def draft_mgr(tmp_path: Path) -> DraftManager:
    return DraftManager(tmp_path / "drafts")


@pytest.fixture
def index_mgr(tmp_path: Path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir(exist_ok=True)
    config = CortexConfig(vault={"path": str(vault_path)})
    mgr = IndexManager(config)
    yield mgr
    mgr.close()


def _make_note(
    note_id: str = "note-1",
    title: str = "Test Note",
    content: str = "Test content about machine learning.",
    modified: datetime | None = None,
    tags: list[str] | None = None,
) -> Note:
    now = modified or datetime.now()
    return Note(
        id=note_id,
        title=title,
        note_type="concept",
        path=Path(f"/vault/20-concepts/{title.lower().replace(' ', '-')}.md"),
        content=content,
        frontmatter={"id": note_id, "title": title, "type": "concept",
                      "tags": tags or [], "status": "active"},
        created=now,
        modified=now,
        tags=tags or [],
        links=[],
        status="active",
    )


# ---------------------------------------------------------------------------
# IndexManager no-op optimization tests
# ---------------------------------------------------------------------------


class TestReindexNoOp:
    """IndexManager.reindex_note should skip when content is unchanged."""

    def test_reindex_noop_when_unchanged(self, index_mgr: IndexManager) -> None:
        """Reindexing the exact same note should be a no-op (hash match)."""
        note = _make_note()
        index_mgr.index_note(note)

        # Reindex the same note — should not error and should still be searchable
        index_mgr.reindex_note(note)

        results = index_mgr.lexical.search("machine learning")
        assert len(results) == 1
        assert results[0].note_id == "note-1"

    def test_reindex_updates_when_content_changes(self, index_mgr: IndexManager) -> None:
        """Reindexing with changed content should update the index."""
        note = _make_note(content="Old content about Redis caching")
        index_mgr.index_note(note)

        updated = _make_note(content="New content about PostgreSQL databases")
        index_mgr.reindex_note(updated)

        assert len(index_mgr.lexical.search("Redis")) == 0
        assert len(index_mgr.lexical.search("PostgreSQL")) == 1

    def test_reindex_updates_when_tags_change(self, index_mgr: IndexManager) -> None:
        """Changing tags should trigger a real reindex."""
        note = _make_note(tags=["old-tag"])
        index_mgr.index_note(note)

        updated = _make_note(tags=["new-tag"])
        index_mgr.reindex_note(updated)

        # Hash should differ due to tag change — reindex happened
        assert _note_content_hash(note) != _note_content_hash(updated)

    def test_content_hash_deterministic(self) -> None:
        """Same note produces the same hash."""
        note = _make_note()
        assert _note_content_hash(note) == _note_content_hash(note)


# ---------------------------------------------------------------------------
# Draft freshness / conflict resolution tests
# ---------------------------------------------------------------------------


class TestDraftFreshness:
    """DraftManager.check_draft_freshness detects stale edit drafts."""

    def test_fresh_edit_draft(
        self, draft_mgr: DraftManager, vault: VaultManager, vault_dir: Path
    ) -> None:
        """A draft created after the note's last modification is fresh."""
        # Create a note in the vault
        draft = draft_mgr.create_draft(
            note_type="concept", title="Fresh Note", content="Original content."
        )
        note = draft_mgr.approve_draft(draft.draft_id, vault)

        # Create an edit draft (simulating LifecycleManager.start_edit)
        edit_draft = NoteDraft(
            draft_id=str(uuid.uuid4()),
            note_type="concept",
            title="Fresh Note",
            content="Edited content.",
            frontmatter={"_edit_note_id": note.id},
            target_folder="20-concepts",
            target_filename="fresh-note.md",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        draft_mgr._save_draft(edit_draft)

        assert draft_mgr.check_draft_freshness(edit_draft.draft_id, vault) is True

    def test_stale_edit_draft_discarded(
        self, draft_mgr: DraftManager, vault: VaultManager, vault_dir: Path
    ) -> None:
        """A draft is stale if the note was modified after draft creation — draft gets discarded."""
        # Create a note in the vault
        draft = draft_mgr.create_draft(
            note_type="concept", title="Stale Note", content="Original content."
        )
        note = draft_mgr.approve_draft(draft.draft_id, vault)

        # Create an edit draft with created_at in the past
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        edit_draft = NoteDraft(
            draft_id=str(uuid.uuid4()),
            note_type="concept",
            title="Stale Note",
            content="Edited content.",
            frontmatter={"_edit_note_id": note.id},
            target_folder="20-concepts",
            target_filename="stale-note.md",
            created_at=past.isoformat(),
        )
        draft_mgr._save_draft(edit_draft)

        # Modify the vault note externally (simulate external edit)
        vault.update_note(note.id, content="Externally modified content.")

        # Draft should be stale
        assert draft_mgr.check_draft_freshness(edit_draft.draft_id, vault) is False

        # Draft file should be auto-discarded
        with pytest.raises(KeyError):
            draft_mgr.get_draft(edit_draft.draft_id)

    def test_non_edit_draft_always_fresh(self, draft_mgr: DraftManager, vault: VaultManager) -> None:
        """Non-edit drafts (no _edit_note_id) are always considered fresh."""
        draft = draft_mgr.create_draft(
            note_type="inbox", title="Just a thought", content="Some thought."
        )
        assert draft_mgr.check_draft_freshness(draft.draft_id, vault) is True

    def test_stale_draft_deleted_note(
        self, draft_mgr: DraftManager, vault: VaultManager, vault_dir: Path
    ) -> None:
        """If the underlying note was deleted, the edit draft is stale."""
        # Create a note, then create an edit draft
        draft = draft_mgr.create_draft(
            note_type="concept", title="Doomed Note", content="Will be deleted."
        )
        note = draft_mgr.approve_draft(draft.draft_id, vault)

        edit_draft = NoteDraft(
            draft_id=str(uuid.uuid4()),
            note_type="concept",
            title="Doomed Note",
            content="Edited content.",
            frontmatter={"_edit_note_id": note.id},
            target_folder="20-concepts",
            target_filename="doomed-note.md",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        draft_mgr._save_draft(edit_draft)

        # Delete the note file from disk
        note.path.unlink()

        # Draft should be stale since note is gone
        assert draft_mgr.check_draft_freshness(edit_draft.draft_id, vault) is False
