"""Frontmatter parser — parses markdown files with YAML frontmatter into Note dataclass instances."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import frontmatter

# Regex patterns for link and tag extraction
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_INLINE_TAG_RE = re.compile(r"(?:^|(?<=\s))#([A-Za-z\u00C0-\u024F\u3000-\u9FFF][\w/\-\u00C0-\u024F\u3000-\u9FFF]*)", re.UNICODE)
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```|`[^`\n]+`")


@dataclass
class Link:
    """Represents a link between notes."""

    source_id: str
    target_id: str
    target_title: str
    link_type: str  # "wikilink" or "markdown"


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
    links: list[Link] = field(default_factory=list)
    status: str = "active"
    supersedes: str | None = None
    superseded_by: str | None = None
    archived_date: datetime | None = None


def extract_wikilinks(content: str) -> list[str]:
    """Extract wikilink targets from content. Handles [[target]] and [[target|alias]]."""
    return _WIKILINK_RE.findall(content)


def extract_markdown_links(content: str) -> list[tuple[str, str]]:
    """Extract markdown links as (text, url) tuples from content."""
    return _MARKDOWN_LINK_RE.findall(content)


def extract_inline_tags(content: str) -> list[str]:
    """Extract #tag from body text, excluding tags inside code blocks."""
    # Remove code blocks first
    cleaned = _CODE_BLOCK_RE.sub("", content)
    return _INLINE_TAG_RE.findall(cleaned)


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

    note_id = fm.get("id", str(uuid4()))

    # Extract wikilinks and build Link objects
    wikilink_targets = extract_wikilinks(post.content)
    links = [
        Link(source_id=note_id, target_id=target, target_title=target, link_type="wikilink")
        for target in wikilink_targets
    ]

    # Merge frontmatter tags with inline tags (deduplicated, order preserved)
    inline_tags = extract_inline_tags(post.content)
    all_tags = list(dict.fromkeys(tags + inline_tags))

    return Note(
        id=note_id,
        title=fm.get("title", path.stem),
        note_type=fm.get("type", "inbox"),
        path=path,
        content=post.content,
        frontmatter=fm,
        created=created,
        modified=modified,
        tags=all_tags,
        links=links,
        status=fm.get("status", "active"),
        supersedes=fm.get("supersedes"),
        superseded_by=fm.get("superseded_by"),
        archived_date=archived_date,
    )
