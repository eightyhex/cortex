"""LifecycleManager — edit-with-review flow for vault notes."""

from __future__ import annotations

import difflib
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from cortex.capture.draft import DraftManager, NoteDraft, _TYPE_TO_FOLDER

if TYPE_CHECKING:
    from cortex.graph.manager import GraphManager
    from cortex.index.manager import IndexManager
    from cortex.vault.manager import VaultManager
    from cortex.vault.parser import Note


class LifecycleManager:
    """Orchestrates note lifecycle operations: edit, archive, supersede."""

    def __init__(
        self,
        vault: VaultManager,
        index: IndexManager,
        graph: GraphManager,
        draft_mgr: DraftManager,
    ) -> None:
        self.vault = vault
        self.index = index
        self.graph = graph
        self.draft_mgr = draft_mgr

    def start_edit(self, note_id: str, changes: dict) -> NoteDraft:
        """Load a note, apply changes to create a draft with diff preview.

        Args:
            note_id: ID of the note to edit.
            changes: Dict with optional keys: title, content, tags, and
                     arbitrary frontmatter overrides.

        Returns:
            A NoteDraft showing the proposed changes with a diff.
        """
        note = self.vault.get_note(note_id)

        # Build the new state
        new_title = changes.get("title", note.title)
        new_content = changes.get("content", note.content)
        new_tags = changes.get("tags", list(note.tags))

        # Build frontmatter preserving existing fields
        new_frontmatter = dict(note.frontmatter)
        if "title" in changes:
            new_frontmatter["title"] = new_title
        if "tags" in changes:
            new_frontmatter["tags"] = list(new_tags)

        # Apply any other frontmatter overrides
        for key, value in changes.items():
            if key not in ("title", "content", "tags"):
                new_frontmatter[key] = value

        # Determine target folder from note type
        target_folder = _TYPE_TO_FOLDER.get(note.note_type, "00-inbox")

        # Compute the filename from the existing path
        target_filename = note.path.name

        # Generate diff between old and new content
        old_lines = note.content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines, fromfile="before", tofile="after", lineterm=""
        )
        diff_text = "\n".join(diff)

        import uuid

        draft_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        draft = NoteDraft(
            draft_id=draft_id,
            note_type=note.note_type,
            title=new_title,
            content=new_content,
            frontmatter=new_frontmatter,
            target_folder=target_folder,
            target_filename=target_filename,
            created_at=now.isoformat(),
        )

        # Attach diff and source note_id as extra metadata
        draft.frontmatter["_edit_note_id"] = note_id
        draft.frontmatter["_diff"] = diff_text

        # Save draft via DraftManager
        self.draft_mgr._save_draft(draft)

        return draft

    def commit_edit(self, draft_id: str) -> Note:
        """Approve a draft edit: update the note in vault, re-index everywhere.

        Args:
            draft_id: The draft to commit.

        Returns:
            The updated Note.
        """
        draft = self.draft_mgr.get_draft(draft_id)

        note_id = draft.frontmatter.get("_edit_note_id")
        if not note_id:
            raise ValueError("Draft is not an edit draft (missing _edit_note_id)")

        # Build metadata from frontmatter, excluding internal fields
        metadata = {
            k: v for k, v in draft.frontmatter.items()
            if not k.startswith("_")
        }

        # Update the note in the vault
        updated_note = self.vault.update_note(
            note_id,
            content=draft.content,
            metadata=metadata,
        )

        # Re-index in all stores
        self.index.reindex_note(updated_note)
        self.graph.update_note(updated_note)

        # Clean up draft
        self.draft_mgr.reject_draft(draft_id)

        return updated_note
