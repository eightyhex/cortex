"""Frontmatter parser — parses markdown files with YAML frontmatter into Note dataclass instances."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import frontmatter


@dataclass
class Note:
    """Represents a parsed vault note."""

    id: str
    title: str
    note_type: str
    path: Path
    content: str
    frontmatter: dict
    created: datetime
    modified: datetime
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    status: str = "active"
    supersedes: str | None = None
    superseded_by: str | None = None
    archived_date: datetime | None = None


def parse_note(path: Path) -> Note:
    """Parse a markdown file with YAML frontmatter into a Note dataclass.

    Handles missing frontmatter, missing fields, and empty files gracefully.
    """
    text = path.read_text(encoding="utf-8") if path.exists() else ""

    if not text.strip():
        now = datetime.now()
        return Note(
            id=str(uuid4()),
            title=path.stem,
            note_type="inbox",
            path=path,
            content="",
            frontmatter={},
            created=now,
            modified=now,
        )

    post = frontmatter.loads(text)
    fm = dict(post.metadata)

    now = datetime.now()

    created = fm.get("created")
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    elif not isinstance(created, datetime):
        created = now

    modified = fm.get("modified")
    if isinstance(modified, str):
        modified = datetime.fromisoformat(modified)
    elif not isinstance(modified, datetime):
        modified = now

    archived_date = fm.get("archived_date")
    if isinstance(archived_date, str):
        archived_date = datetime.fromisoformat(archived_date)
    elif not isinstance(archived_date, datetime):
        archived_date = None

    tags = fm.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return Note(
        id=fm.get("id", str(uuid4())),
        title=fm.get("title", path.stem),
        note_type=fm.get("type", "inbox"),
        path=path,
        content=post.content,
        frontmatter=fm,
        created=created,
        modified=modified,
        tags=tags,
        links=[],
        status=fm.get("status", "active"),
        supersedes=fm.get("supersedes"),
        superseded_by=fm.get("superseded_by"),
        archived_date=archived_date,
    )
