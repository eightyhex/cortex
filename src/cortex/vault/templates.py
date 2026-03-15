"""Note template rendering for each note type.

Given a note type and metadata, produces the full markdown string
(YAML frontmatter + body) compatible with Obsidian.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import yaml

# All supported note types
NOTE_TYPES = frozenset(
    {"inbox", "daily", "task", "source", "concept", "permanent", "project", "review"}
)

# Body templates per note type (content placeholder is inserted by the renderer)
_BODY_TEMPLATES: dict[str, str] = {
    "inbox": "{content}",
    "daily": (
        "## Plan\n\n{content}\n\n"
        "## Log\n\n"
        "## Reflections\n"
    ),
    "task": (
        "## Description\n\n{content}\n\n"
        "## Subtasks\n\n- [ ] \n\n"
        "## Notes\n"
    ),
    "source": (
        "## Summary\n\n\n\n"
        "## Key Points\n\n- \n\n"
        "## My Notes\n\n{content}\n\n"
        "## Related\n"
    ),
    "concept": (
        "## Definition\n\n{content}\n\n"
        "## Examples\n\n"
        "## Connections\n\n"
        "## Sources\n"
    ),
    "permanent": (
        "{content}\n\n"
        "## Evidence\n\n"
        "## Related\n\n"
        "## Open Questions\n"
    ),
    "project": (
        "## Goal\n\n{content}\n\n"
        "## Tasks\n\n"
        "## Notes\n\n"
        "## Resources\n"
    ),
    "review": (
        "## Summary\n\n{content}\n\n"
        "## Highlights\n\n"
        "## Challenges\n\n"
        "## Next Steps\n"
    ),
}


def render_template(
    note_type: str,
    title: str,
    tags: list[str] | None = None,
    content: str = "",
    **kwargs: object,
) -> str:
    """Render a note template as YAML frontmatter + markdown body.

    Args:
        note_type: One of the supported note types.
        title: Note title.
        tags: Optional list of tags.
        content: Body content to insert into the template.
        **kwargs: Extra frontmatter fields (e.g. due_date, priority, source_url).

    Returns:
        A string of valid Obsidian-compatible markdown with YAML frontmatter.

    Raises:
        ValueError: If note_type is not supported.
    """
    if note_type not in NOTE_TYPES:
        raise ValueError(
            f"Unknown note type {note_type!r}. Must be one of: {sorted(NOTE_TYPES)}"
        )

    now = datetime.now(timezone.utc)
    note_id = str(uuid.uuid4())

    # Build frontmatter dict
    frontmatter: dict[str, object] = {
        "id": note_id,
        "title": title,
        "type": note_type,
        "created": now.isoformat(),
        "modified": now.isoformat(),
        "tags": list(tags) if tags else [],
        "status": "active",
    }

    # Type-specific fields
    if note_type == "task":
        frontmatter["due_date"] = kwargs.get("due_date", "")
        frontmatter["priority"] = kwargs.get("priority", "medium")
    elif note_type == "source":
        frontmatter["source_url"] = kwargs.get("source_url", "")

    # Render body
    body_template = _BODY_TEMPLATES[note_type]
    body = body_template.format(content=content)

    # Build the final markdown
    frontmatter_str = yaml.dump(
        frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    return f"---\n{frontmatter_str}---\n\n{body}\n"
