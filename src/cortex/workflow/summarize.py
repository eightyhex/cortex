"""Source note summarization — extract key sections and metadata for Claude to summarize."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortex.vault.parser import Note


def _extract_headings(content: str) -> list[str]:
    """Extract markdown headings from content."""
    return re.findall(r"^#{1,6}\s+(.+)$", content, re.MULTILINE)


def _extract_urls(content: str) -> list[str]:
    """Extract URLs from content (both markdown links and bare URLs)."""
    # Markdown links
    md_urls = re.findall(r"\[([^\]]*)\]\(([^)]+)\)", content)
    # Bare URLs
    bare_urls = re.findall(r"(?<!\()https?://[^\s\)>]+", content)
    urls: list[str] = []
    for _text, url in md_urls:
        if url not in urls:
            urls.append(url)
    for url in bare_urls:
        if url not in urls:
            urls.append(url)
    return urls


def _word_count(content: str) -> int:
    """Count words in content."""
    return len(content.split()) if content.strip() else 0


def summarize_source(note: Note) -> dict:
    """Extract key sections, metadata, and structure from a source note.

    Returns a dict with structured information for Claude to produce a summary.

    Args:
        note: A parsed Note object (typically of type "source").

    Returns:
        Dict with: note_id, title, note_type, source_url, tags, headings,
        urls, word_count, content_excerpt, created, status.
    """
    content = note.content or ""

    # Extract source URL from frontmatter
    source_url = note.frontmatter.get("source_url", "")

    # Content excerpt (first 500 chars for summary context)
    excerpt = content.strip()
    if len(excerpt) > 500:
        excerpt = excerpt[:500].rsplit(" ", 1)[0] + "…"

    return {
        "note_id": note.id,
        "title": note.title,
        "note_type": note.note_type,
        "source_url": source_url,
        "tags": list(note.tags),
        "headings": _extract_headings(content),
        "urls": _extract_urls(content),
        "word_count": _word_count(content),
        "content_excerpt": excerpt,
        "created": note.created.isoformat(),
        "status": note.status,
    }
