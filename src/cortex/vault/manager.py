"""Vault directory management — scaffolding and file operations."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cortex.config import CortexConfig
from cortex.vault.parser import Note, parse_note

VAULT_FOLDERS = [
    "00-inbox",
    "01-daily",
    "02-tasks",
    "10-sources",
    "20-concepts",
    "30-permanent",
    "40-projects",
    "50-reviews",
    "_templates",
]

# Path to the bundled example vault templates
_EXAMPLE_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "vault.example" / "_templates"


def scaffold_vault(vault_path: Path) -> None:
    """Create all required vault folders and copy default templates.

    Idempotent: safe to call multiple times. Folders that already exist
    are left untouched, and template files are only copied when absent.
    """
    vault_path = Path(vault_path)

    # Create the 9 required folders
    for folder in VAULT_FOLDERS:
        (vault_path / folder).mkdir(parents=True, exist_ok=True)

    # Copy template files from vault.example/_templates/ if they don't already exist
    if _EXAMPLE_TEMPLATES_DIR.is_dir():
        templates_dest = vault_path / "_templates"
        for src_file in _EXAMPLE_TEMPLATES_DIR.iterdir():
            if src_file.is_file():
                dest_file = templates_dest / src_file.name
                if not dest_file.exists():
                    shutil.copy2(src_file, dest_file)


class VaultManager:
    """Read and write operations for an Obsidian vault."""

    def __init__(self, vault_path: Path, config: CortexConfig) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.config = config
        if not self.vault_path.is_dir():
            raise FileNotFoundError(f"Vault directory not found: {self.vault_path}")

    def get_note(self, note_id: str) -> Note:
        """Find a note by UUID (scans frontmatter of all vault notes)."""
        for note in self.scan_vault():
            if note.id == note_id:
                return note
        raise KeyError(f"Note not found: {note_id}")

    def get_note_by_path(self, path: Path) -> Note:
        """Parse and return the note at the given path."""
        full_path = path if path.is_absolute() else self.vault_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Note file not found: {full_path}")
        return parse_note(full_path)

    def list_notes(
        self, folder: str | None = None, note_type: str | None = None
    ) -> list[Note]:
        """List all notes, optionally filtered by folder or note_type."""
        notes = self.scan_vault()
        if folder is not None:
            notes = [
                n for n in notes
                if n.path.parent.name == folder
                or str(n.path.relative_to(self.vault_path)).startswith(folder)
            ]
        if note_type is not None:
            notes = [n for n in notes if n.note_type == note_type]
        return notes

    def scan_vault(self) -> list[Note]:
        """Parse all .md files in vault (excludes _templates/)."""
        notes: list[Note] = []
        for md_file in sorted(self.vault_path.rglob("*.md")):
            # Skip _templates directory
            try:
                rel = md_file.relative_to(self.vault_path)
            except ValueError:
                continue
            if rel.parts and rel.parts[0] == "_templates":
                continue
            notes.append(parse_note(md_file))
        return notes

    def create_note(self, draft) -> Note:
        """Write a NoteDraft to the vault and return the parsed Note.

        Creates the target folder if it doesn't exist, writes the rendered
        markdown to disk, and returns the parsed Note.
        """
        target_dir = self.vault_path / draft.target_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / draft.target_filename
        file_path.write_text(draft.render_markdown(), encoding="utf-8")

        return parse_note(file_path)

    def update_note(
        self, note_id: str, content: str | None = None, metadata: dict | None = None
    ) -> Note:
        """Update an existing note's content and/or metadata.

        Finds the note by ID, updates the specified fields, bumps the
        `modified` timestamp, writes the file, and returns the updated Note.
        """
        note = self.get_note(note_id)
        fm = dict(note.frontmatter)

        if metadata:
            fm.update(metadata)

        fm["modified"] = datetime.now(timezone.utc).isoformat()

        body = content if content is not None else note.content

        fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        md = f"---\n{fm_str}---\n\n{body}\n"
        note.path.write_text(md, encoding="utf-8")

        return parse_note(note.path)
