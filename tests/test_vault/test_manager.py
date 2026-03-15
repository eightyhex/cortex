"""Tests for VaultManager read operations."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from cortex.config import CortexConfig
from cortex.vault.manager import VaultManager, scaffold_vault


def _write_note(vault: Path, folder: str, filename: str, note_id: str, **kwargs) -> Path:
    """Helper to write a note markdown file with frontmatter."""
    note_type = kwargs.get("note_type", "inbox")
    title = kwargs.get("title", filename.replace(".md", ""))
    tags = kwargs.get("tags", [])
    content = kwargs.get("content", "Some content.")

    tags_yaml = "\n".join(f"  - {t}" for t in tags) if tags else ""
    tags_block = f"\ntags:\n{tags_yaml}" if tags else "\ntags: []"

    md = f"""---
id: {note_id}
title: {title}
type: {note_type}
status: active
created: "2026-03-01T10:00:00"
modified: "2026-03-01T10:00:00"{tags_block}
---

{content}
"""
    path = vault / folder / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    return path


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    """Create a scaffolded vault with sample notes."""
    vault = tmp_path / "vault"
    scaffold_vault(vault)

    _write_note(vault, "00-inbox", "thought1.md", "id-inbox-1", note_type="inbox", title="Quick thought")
    _write_note(vault, "00-inbox", "thought2.md", "id-inbox-2", note_type="inbox", title="Another thought")
    _write_note(vault, "20-concepts", "ml-basics.md", "id-concept-1", note_type="concept", title="ML Basics", tags=["ml", "ai"])
    _write_note(vault, "10-sources", "paper.md", "id-source-1", note_type="source", title="Research Paper", tags=["research"])
    _write_note(vault, "02-tasks", "todo.md", "id-task-1", note_type="task", title="Fix bug")

    return vault


@pytest.fixture()
def manager(vault_dir: Path) -> VaultManager:
    config = CortexConfig(vault={"path": str(vault_dir)})
    return VaultManager(vault_dir, config)


class TestVaultManagerInit:
    def test_init_with_valid_path(self, vault_dir: Path) -> None:
        config = CortexConfig()
        vm = VaultManager(vault_dir, config)
        assert vm.vault_path == vault_dir

    def test_init_with_missing_path_raises(self, tmp_path: Path) -> None:
        config = CortexConfig()
        with pytest.raises(FileNotFoundError, match="Vault directory not found"):
            VaultManager(tmp_path / "nonexistent", config)


class TestScanVault:
    def test_scan_returns_all_notes(self, manager: VaultManager) -> None:
        notes = manager.scan_vault()
        assert len(notes) == 5

    def test_scan_excludes_templates(self, vault_dir: Path, manager: VaultManager) -> None:
        # Write a file in _templates — should be excluded
        tpl = vault_dir / "_templates" / "test.md"
        tpl.write_text("---\ntitle: template\n---\nBody", encoding="utf-8")
        notes = manager.scan_vault()
        # Verify no note comes from _templates/ folder (check path parts, not substring)
        for n in notes:
            rel = n.path.relative_to(manager.vault_path)
            assert rel.parts[0] != "_templates", f"Template file not excluded: {n.path}"


class TestGetNote:
    def test_get_note_by_id(self, manager: VaultManager) -> None:
        note = manager.get_note("id-concept-1")
        assert note.title == "ML Basics"
        assert note.note_type == "concept"

    def test_get_note_missing_raises(self, manager: VaultManager) -> None:
        with pytest.raises(KeyError, match="Note not found"):
            manager.get_note("nonexistent-id")


class TestGetNoteByPath:
    def test_get_note_by_relative_path(self, manager: VaultManager) -> None:
        note = manager.get_note_by_path(Path("20-concepts/ml-basics.md"))
        assert note.title == "ML Basics"
        assert "ml" in note.tags

    def test_get_note_by_absolute_path(self, vault_dir: Path, manager: VaultManager) -> None:
        full = vault_dir / "02-tasks" / "todo.md"
        note = manager.get_note_by_path(full)
        assert note.title == "Fix bug"

    def test_get_note_by_path_missing_raises(self, manager: VaultManager) -> None:
        with pytest.raises(FileNotFoundError, match="Note file not found"):
            manager.get_note_by_path(Path("missing/file.md"))


class TestListNotes:
    def test_list_all(self, manager: VaultManager) -> None:
        notes = manager.list_notes()
        assert len(notes) == 5

    def test_list_by_folder(self, manager: VaultManager) -> None:
        notes = manager.list_notes(folder="00-inbox")
        assert len(notes) == 2
        assert all(n.note_type == "inbox" for n in notes)

    def test_list_by_note_type(self, manager: VaultManager) -> None:
        notes = manager.list_notes(note_type="source")
        assert len(notes) == 1
        assert notes[0].title == "Research Paper"

    def test_list_by_folder_and_type(self, manager: VaultManager) -> None:
        notes = manager.list_notes(folder="00-inbox", note_type="inbox")
        assert len(notes) == 2

    def test_list_empty_result(self, manager: VaultManager) -> None:
        notes = manager.list_notes(note_type="project")
        assert notes == []
