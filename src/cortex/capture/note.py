"""Generic note creation for concept, permanent, and project types."""

from __future__ import annotations

from cortex.capture.draft import DraftManager, NoteDraft


def create_note(
    draft_manager: DraftManager,
    note_type: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
) -> NoteDraft:
    """Create a generic note draft (concept, permanent, project, etc.).

    Args:
        draft_manager: DraftManager instance for persistence.
        note_type: The note type (concept, permanent, project, etc.).
        title: Note title.
        content: Note body content.
        tags: Optional tags.

    Returns:
        A NoteDraft ready for review and approval.
    """
    metadata: dict = {}
    if tags:
        metadata["tags"] = tags

    return draft_manager.create_draft(
        note_type=note_type,
        title=title,
        content=content,
        metadata=metadata,
    )
