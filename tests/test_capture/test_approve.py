"""Tests for DraftManager.approve_draft integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.capture.draft import DraftManager
from cortex.config import CortexConfig
from cortex.vault.manager import VaultManager, scaffold_vault


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    """Create a scaffolded vault in a temp directory."""
    vault = tmp_path / "vault"
    scaffold_vault(vault)
    return vault


@pytest.fixture
def vault(vault_dir: Path) -> VaultManager:
    """Return a VaultManager pointed at the temp vault."""
    config = CortexConfig()
    return VaultManager(vault_dir, config)


@pytest.fixture
def draft_mgr(tmp_path: Path) -> DraftManager:
    """Return a DraftManager using a temp drafts directory."""
    return DraftManager(tmp_path / "drafts")


def test_approve_creates_file(draft_mgr: DraftManager, vault: VaultManager, vault_dir: Path):
    """Approving a draft writes the .md file to the vault at the correct path."""
    draft = draft_mgr.create_draft(
        note_type="inbox",
        title="Test Approval",
        content="This note was approved.",
        metadata={"tags": ["test"]},
    )

    note = draft_mgr.approve_draft(draft.draft_id, vault)

    expected_path = vault_dir / draft.target_folder / draft.target_filename
    assert expected_path.exists()
    assert note.path == expected_path
    assert note.title == "Test Approval"
    assert "This note was approved." in expected_path.read_text()


def test_approve_deletes_draft(draft_mgr: DraftManager, vault: VaultManager):
    """After approval, the draft JSON file should be deleted."""
    draft = draft_mgr.create_draft(
        note_type="concept",
        title="Ephemeral Draft",
        content="Will be removed after approval.",
    )
    draft_path = draft_mgr._drafts_dir / f"{draft.draft_id}.json"
    assert draft_path.exists()

    draft_mgr.approve_draft(draft.draft_id, vault)

    assert not draft_path.exists()
    with pytest.raises(KeyError):
        draft_mgr.get_draft(draft.draft_id)


def test_approve_returns_valid_note(draft_mgr: DraftManager, vault: VaultManager):
    """The returned Note has correct fields populated from the draft."""
    draft = draft_mgr.create_draft(
        note_type="task",
        title="Buy groceries",
        content="Milk, eggs, bread",
        metadata={"tags": ["errands"], "due_date": "2026-03-20", "priority": "high"},
    )

    note = draft_mgr.approve_draft(draft.draft_id, vault)

    assert note.id == draft.frontmatter["id"]
    assert note.title == "Buy groceries"
    assert note.note_type == "task"
    assert "errands" in note.tags
    assert "Milk, eggs, bread" in note.content


def test_approve_nonexistent_draft_raises(draft_mgr: DraftManager, vault: VaultManager):
    """Approving a draft that doesn't exist raises KeyError."""
    with pytest.raises(KeyError):
        draft_mgr.approve_draft("nonexistent-id", vault)
