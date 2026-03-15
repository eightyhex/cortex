"""Tests for vault directory scaffolding."""

from __future__ import annotations

from pathlib import Path

from cortex.vault.manager import VAULT_FOLDERS, scaffold_vault


def test_scaffold_creates_all_folders(tmp_path: Path) -> None:
    """scaffold_vault creates all 9 required folders."""
    vault = tmp_path / "vault"
    scaffold_vault(vault)

    for folder in VAULT_FOLDERS:
        assert (vault / folder).is_dir(), f"Missing folder: {folder}"


def test_scaffold_is_idempotent(tmp_path: Path) -> None:
    """Calling scaffold_vault twice does not error or alter existing content."""
    vault = tmp_path / "vault"
    scaffold_vault(vault)

    # Drop a custom file into a folder to prove it survives a second scaffold
    marker = vault / "00-inbox" / "keep-me.md"
    marker.write_text("hello")

    scaffold_vault(vault)

    assert marker.read_text() == "hello"
    for folder in VAULT_FOLDERS:
        assert (vault / folder).is_dir()


def test_scaffold_copies_template_files(tmp_path: Path) -> None:
    """Template files from vault.example/_templates/ are copied on first scaffold."""
    vault = tmp_path / "vault"
    scaffold_vault(vault)

    templates_dir = vault / "_templates"
    template_files = list(templates_dir.glob("*.md"))
    # vault.example/_templates/ contains at least inbox.md, task.md, etc.
    assert len(template_files) >= 1, "No template files were copied"


def test_scaffold_does_not_overwrite_existing_templates(tmp_path: Path) -> None:
    """Existing template files are not overwritten by a second scaffold."""
    vault = tmp_path / "vault"
    scaffold_vault(vault)

    # Modify a template
    inbox_tmpl = vault / "_templates" / "inbox.md"
    if inbox_tmpl.exists():
        inbox_tmpl.write_text("custom content")

        scaffold_vault(vault)

        assert inbox_tmpl.read_text() == "custom content"
