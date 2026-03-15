"""Vault directory management — scaffolding and file operations."""

from __future__ import annotations

import shutil
from pathlib import Path

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
