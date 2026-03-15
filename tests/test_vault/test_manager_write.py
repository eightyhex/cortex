"""Tests for VaultManager write operations (create_note, update_note)."""

from __future__ import annotations

import uuid

import pytest
import yaml

from cortex.capture.draft import DraftManager
from cortex.config import CortexConfig
from cortex.vault.manager import VaultManager, scaffold_vault


@pytest.fixture
def vault_setup(tmp_path):
    """Create a scaffolded vault with a VaultManager and DraftManager."""
    vault_path = tmp_path / "vault"
    scaffold_vault(vault_path)
    config = CortexConfig()
    vm = VaultManager(vault_path, config)
    dm = DraftManager(tmp_path / "drafts")
    return vm, dm, vault_path


class TestCreateNote:
    def test_create_from_draft(self, vault_setup):
        """create_note writes file to disk and returns a parsed Note."""
        vm, dm, vault_path = vault_setup
        draft = dm.create_draft("inbox", "Test Thought", "Some content here", metadata={"tags": ["test"]})

        note = vm.create_note(draft)

        assert note.title == "Test Thought"
        assert note.content == "Some content here"
        assert "test" in note.tags
        assert note.path.exists()
        assert note.path.parent.name == "00-inbox"

    def test_create_ensures_parent_directory(self, vault_setup):
        """create_note creates parent directory if it doesn't exist."""
        vm, dm, vault_path = vault_setup
        # Remove the target folder to test auto-creation
        target = vault_path / "20-concepts"
        if target.exists():
            target.rmdir()

        draft = dm.create_draft("concept", "New Concept", "Concept body")
        note = vm.create_note(draft)

        assert note.path.exists()
        assert note.path.parent.name == "20-concepts"

    def test_create_file_content_matches_draft(self, vault_setup):
        """The file on disk matches the rendered markdown from the draft."""
        vm, dm, vault_path = vault_setup
        draft = dm.create_draft("task", "Buy groceries", "Milk, eggs, bread", metadata={"tags": ["errands"], "priority": "high"})

        note = vm.create_note(draft)
        raw = note.path.read_text(encoding="utf-8")

        assert "Buy groceries" in raw
        assert "Milk, eggs, bread" in raw
        assert "errands" in raw


class TestUpdateNote:
    def test_update_content(self, vault_setup):
        """update_note replaces the note body."""
        vm, dm, _ = vault_setup
        draft = dm.create_draft("inbox", "Original", "Old content")
        note = vm.create_note(draft)

        updated = vm.update_note(note.id, content="New content")

        assert updated.content == "New content"
        assert updated.title == "Original"

    def test_update_metadata(self, vault_setup):
        """update_note merges metadata into frontmatter."""
        vm, dm, _ = vault_setup
        draft = dm.create_draft("inbox", "Meta Test", "Body")
        note = vm.create_note(draft)

        updated = vm.update_note(note.id, metadata={"tags": ["updated", "new"]})

        assert "updated" in updated.tags
        assert "new" in updated.tags

    def test_update_bumps_modified(self, vault_setup):
        """update_note updates the modified timestamp."""
        vm, dm, _ = vault_setup
        draft = dm.create_draft("inbox", "Timestamp", "Body")
        note = vm.create_note(draft)
        original_modified = note.modified

        updated = vm.update_note(note.id, content="Changed")

        assert updated.modified != original_modified

    def test_update_persists_to_disk(self, vault_setup):
        """update_note writes changes to the actual file."""
        vm, dm, _ = vault_setup
        draft = dm.create_draft("inbox", "Disk Test", "Before")
        note = vm.create_note(draft)

        vm.update_note(note.id, content="After")

        raw = note.path.read_text(encoding="utf-8")
        assert "After" in raw
        assert "Before" not in raw
