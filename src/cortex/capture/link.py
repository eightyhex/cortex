"""Capture a web link as a source note."""

from __future__ import annotations

from cortex.capture.draft import DraftManager, NoteDraft


def save_link(
    draft_manager: DraftManager,
    url: str,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> NoteDraft:
    """Create a source note draft from a URL.

    Args:
        draft_manager: DraftManager instance for persistence.
        url: The URL to save.
        title: Optional title. Defaults to the URL.
        description: Optional description/notes about the link.
        tags: Optional tags.

    Returns:
        A NoteDraft ready for review and approval.
    """
    metadata: dict = {"source_url": url}
    if tags:
        metadata["tags"] = tags

    return draft_manager.create_draft(
        note_type="source",
        title=title or url,
        content=description or "",
        metadata=metadata,
    )
