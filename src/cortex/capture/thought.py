"""Capture a quick thought into the inbox."""

from __future__ import annotations

from cortex.capture.draft import DraftManager, NoteDraft


def capture_thought(
    draft_manager: DraftManager,
    content: str,
    tags: list[str] | None = None,
) -> NoteDraft:
    """Create an inbox note draft from a quick thought.

    Args:
        draft_manager: DraftManager instance for persistence.
        content: The thought content.
        tags: Optional tags.

    Returns:
        A NoteDraft ready for review and approval.
    """
    # Use the first line (up to 60 chars) as the title
    first_line = content.split("\n", 1)[0].strip()
    title = first_line[:60] if first_line else "Untitled thought"

    metadata: dict = {}
    if tags:
        metadata["tags"] = tags

    return draft_manager.create_draft(
        note_type="inbox",
        title=title,
        content=content,
        metadata=metadata,
    )
