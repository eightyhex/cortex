"""Inbox processing workflow — list and suggest categorization for inbox items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from cortex.vault.manager import VaultManager
from cortex.vault.parser import Note


# Suggested target folders based on simple content heuristics
_TYPE_SUGGESTIONS: list[tuple[str, str, str]] = [
    # (keyword/pattern, suggested_type, suggested_folder)
    ("http://", "source", "10-sources"),
    ("https://", "source", "10-sources"),
    ("TODO", "task", "02-tasks"),
    ("FIXME", "task", "02-tasks"),
    ("[ ]", "task", "02-tasks"),
    ("[x]", "task", "02-tasks"),
]

_DEFAULT_SUGGESTION = ("concept", "20-concepts")


@dataclass
class InboxItem:
    """An inbox note with categorization suggestions."""

    note_id: str
    title: str
    summary: str
    suggested_type: str
    suggested_folder: str
    suggested_tags: list[str]
    age_days: int
    path: str


def _summarize(note: Note, max_length: int = 200) -> str:
    """Extract a short summary from the note content."""
    text = note.content.strip()
    if not text:
        return "(empty note)"
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "…"


def _suggest_type_and_folder(note: Note) -> tuple[str, str]:
    """Suggest a target type and folder based on note content."""
    content_upper = note.content.upper()
    content = note.content

    for keyword, stype, folder in _TYPE_SUGGESTIONS:
        if keyword.upper() in content_upper or keyword in content:
            return stype, folder

    return _DEFAULT_SUGGESTION


def _suggest_tags(note: Note) -> list[str]:
    """Return existing tags from the note as suggested tags."""
    return list(note.tags) if note.tags else []


def process_inbox(vault: VaultManager) -> list[InboxItem]:
    """List all notes in 00-inbox/ with categorization suggestions.

    Returns a list of InboxItem objects sorted by age (oldest first).
    """
    notes = vault.list_notes(folder="00-inbox")
    now = datetime.now(timezone.utc)

    items: list[InboxItem] = []
    for note in notes:
        created = note.created
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - created).days)

        suggested_type, suggested_folder = _suggest_type_and_folder(note)
        suggested_tags = _suggest_tags(note)

        items.append(
            InboxItem(
                note_id=note.id,
                title=note.title,
                summary=_summarize(note),
                suggested_type=suggested_type,
                suggested_folder=suggested_folder,
                suggested_tags=suggested_tags,
                age_days=age_days,
                path=str(note.path),
            )
        )

    # Sort by age descending (oldest first)
    items.sort(key=lambda item: item.age_days, reverse=True)
    return items
