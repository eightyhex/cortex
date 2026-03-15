"""Draft system — in-memory draft generation with file-based persistence.

Implements the review-before-create flow: capture commands produce a NoteDraft,
which is persisted as JSON. Only after explicit approval is a note written to the vault.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cortex.vault.templates import NOTE_TYPES, render_template

# Mapping from note_type to vault folder
_TYPE_TO_FOLDER: dict[str, str] = {
    "inbox": "00-inbox",
    "daily": "01-daily",
    "task": "02-tasks",
    "source": "10-sources",
    "concept": "20-concepts",
    "permanent": "30-permanent",
    "project": "40-projects",
    "review": "50-reviews",
}

# Max age for stale drafts (24 hours in seconds)
_STALE_THRESHOLD_SECS = 24 * 60 * 60


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len].rstrip("-")


def _generate_filename(note_type: str, title: str, draft_id: str) -> str:
    """Generate filename: {date}-{type}-{short-hash}-{slug}.md"""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    short_hash = draft_id.replace("-", "")[:4]
    slug = _slugify(title)
    return f"{date_str}-{note_type}-{short_hash}-{slug}.md"


@dataclass
class NoteDraft:
    """An in-memory note that has not been saved to the vault yet."""

    draft_id: str
    note_type: str
    title: str
    content: str
    frontmatter: dict
    target_folder: str
    target_filename: str
    created_at: str  # ISO datetime

    def render_preview(self) -> str:
        """Render the draft as a formatted preview string for Claude to show the user."""
        tags = self.frontmatter.get("tags", [])
        tags_str = ", ".join(f"#{t}" for t in tags) if tags else "(none)"

        lines = [
            f"## {self.note_type.capitalize()} Note",
            f"**Title:** {self.title}",
            f"**Type:** {self.note_type}",
            f"**Tags:** {tags_str}",
            f"**Folder:** {self.target_folder}/",
            f"**File:** {self.target_filename}",
            "",
            "---",
            "",
            self.content if self.content else "(empty)",
        ]
        return "\n".join(lines)

    def render_markdown(self) -> str:
        """Render the full markdown file (frontmatter + body) ready for disk write."""
        fm = dict(self.frontmatter)
        fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return f"---\n{fm_str}---\n\n{self.content}\n"

    def apply_edits(self, edits: dict) -> NoteDraft:
        """Return a new NoteDraft with user-requested changes applied.

        Supported edits: title, content, tags, folder, and arbitrary frontmatter overrides.
        """
        new_title = edits.get("title", self.title)
        new_content = edits.get("content", self.content)
        new_frontmatter = dict(self.frontmatter)
        new_folder = edits.get("folder", self.target_folder)

        if "tags" in edits:
            new_frontmatter["tags"] = list(edits["tags"])

        if "title" in edits:
            new_frontmatter["title"] = new_title

        # Update modified timestamp
        new_frontmatter["modified"] = datetime.now(timezone.utc).isoformat()

        # Regenerate filename if title changed
        new_filename = self.target_filename
        if "title" in edits:
            new_filename = _generate_filename(self.note_type, new_title, self.draft_id)

        return NoteDraft(
            draft_id=self.draft_id,
            note_type=self.note_type,
            title=new_title,
            content=new_content,
            frontmatter=new_frontmatter,
            target_folder=new_folder,
            target_filename=new_filename,
            created_at=self.created_at,
        )


class DraftManager:
    """Manages the lifecycle of note drafts with file-based persistence."""

    def __init__(self, drafts_dir: Path) -> None:
        self._drafts_dir = Path(drafts_dir)
        self._drafts_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_drafts()

    def _cleanup_stale_drafts(self) -> None:
        """Remove draft files older than 24 hours."""
        now = time.time()
        for draft_file in self._drafts_dir.glob("*.json"):
            if now - draft_file.stat().st_mtime > _STALE_THRESHOLD_SECS:
                draft_file.unlink()

    def create_draft(
        self,
        note_type: str,
        title: str,
        content: str,
        metadata: dict | None = None,
    ) -> NoteDraft:
        """Generate a draft using templates. Persist to drafts_dir/{draft_id}.json."""
        if note_type not in NOTE_TYPES:
            raise ValueError(
                f"Unknown note type {note_type!r}. Must be one of: {sorted(NOTE_TYPES)}"
            )

        metadata = metadata or {}
        draft_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Build frontmatter
        note_id = str(uuid.uuid4())
        frontmatter: dict = {
            "id": note_id,
            "title": title,
            "type": note_type,
            "created": now.isoformat(),
            "modified": now.isoformat(),
            "tags": list(metadata.get("tags", [])),
            "status": "active",
        }

        # Type-specific fields
        if note_type == "task":
            frontmatter["due_date"] = metadata.get("due_date", "")
            frontmatter["priority"] = metadata.get("priority", "medium")
        elif note_type == "source":
            frontmatter["source_url"] = metadata.get("source_url", "")

        target_folder = _TYPE_TO_FOLDER.get(note_type, "00-inbox")
        target_filename = _generate_filename(note_type, title, draft_id)

        draft = NoteDraft(
            draft_id=draft_id,
            note_type=note_type,
            title=title,
            content=content,
            frontmatter=frontmatter,
            target_folder=target_folder,
            target_filename=target_filename,
            created_at=now.isoformat(),
        )

        self._save_draft(draft)
        return draft

    def get_draft(self, draft_id: str) -> NoteDraft:
        """Retrieve a pending draft from file."""
        path = self._drafts_dir / f"{draft_id}.json"
        if not path.exists():
            raise KeyError(f"Draft not found: {draft_id}")
        return self._load_draft(path)

    def update_draft(self, draft_id: str, edits: dict) -> NoteDraft:
        """Apply user edits, save updated draft, and return the updated draft."""
        draft = self.get_draft(draft_id)
        updated = draft.apply_edits(edits)
        self._save_draft(updated)
        return updated

    def reject_draft(self, draft_id: str) -> None:
        """Discard a draft. Deletes the draft file."""
        path = self._drafts_dir / f"{draft_id}.json"
        if path.exists():
            path.unlink()

    def _save_draft(self, draft: NoteDraft) -> None:
        """Persist draft to JSON file."""
        path = self._drafts_dir / f"{draft.draft_id}.json"
        data = {
            "draft_id": draft.draft_id,
            "note_type": draft.note_type,
            "title": draft.title,
            "content": draft.content,
            "frontmatter": draft.frontmatter,
            "target_folder": draft.target_folder,
            "target_filename": draft.target_filename,
            "created_at": draft.created_at,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _load_draft(self, path: Path) -> NoteDraft:
        """Load a draft from a JSON file."""
        data = json.loads(path.read_text())
        return NoteDraft(
            draft_id=data["draft_id"],
            note_type=data["note_type"],
            title=data["title"],
            content=data["content"],
            frontmatter=data["frontmatter"],
            target_folder=data["target_folder"],
            target_filename=data["target_filename"],
            created_at=data["created_at"],
        )
