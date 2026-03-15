"""Capture a task."""

from __future__ import annotations

from cortex.capture.draft import DraftManager, NoteDraft


def add_task(
    draft_manager: DraftManager,
    title: str,
    description: str | None = None,
    due_date: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
) -> NoteDraft:
    """Create a task note draft.

    Args:
        draft_manager: DraftManager instance for persistence.
        title: Task title.
        description: Optional task description.
        due_date: Optional due date (ISO format string).
        priority: Optional priority (low/medium/high). Defaults to medium.
        tags: Optional tags.

    Returns:
        A NoteDraft ready for review and approval.
    """
    metadata: dict = {}
    if tags:
        metadata["tags"] = tags
    if due_date:
        metadata["due_date"] = due_date
    if priority:
        metadata["priority"] = priority

    return draft_manager.create_draft(
        note_type="task",
        title=title,
        content=description or "",
        metadata=metadata,
    )
