"""Tests for note template rendering."""

from __future__ import annotations

import uuid

import yaml
import pytest

from cortex.vault.templates import render_template, NOTE_TYPES


def _parse_rendered(rendered: str) -> tuple[dict, str]:
    """Split rendered markdown into frontmatter dict and body string."""
    parts = rendered.split("---\n")
    assert len(parts) >= 3, "Expected YAML frontmatter delimiters"
    frontmatter = yaml.safe_load(parts[1])
    body = "---\n".join(parts[2:]).strip()
    return frontmatter, body


class TestRenderTemplate:
    """Core rendering tests."""

    def test_inbox_note(self):
        result = render_template("inbox", "Quick thought", tags=["idea"])
        fm, body = _parse_rendered(result)

        assert fm["title"] == "Quick thought"
        assert fm["type"] == "inbox"
        assert fm["tags"] == ["idea"]
        assert fm["status"] == "active"
        # id is a valid UUID
        uuid.UUID(fm["id"])
        # ISO datetime strings
        assert "T" in fm["created"]
        assert "T" in fm["modified"]

    def test_daily_note(self):
        result = render_template("daily", "2026-03-15", content="Plan the day")
        fm, body = _parse_rendered(result)

        assert fm["type"] == "daily"
        assert "## Plan" in body
        assert "Plan the day" in body
        assert "## Log" in body
        assert "## Reflections" in body

    def test_task_note_with_extra_fields(self):
        result = render_template(
            "task",
            "Fix bug",
            tags=["urgent"],
            content="Something is broken",
            due_date="2026-04-01",
            priority="high",
        )
        fm, body = _parse_rendered(result)

        assert fm["type"] == "task"
        assert fm["due_date"] == "2026-04-01"
        assert fm["priority"] == "high"
        assert "## Description" in body
        assert "Something is broken" in body

    def test_task_note_defaults(self):
        result = render_template("task", "Do something")
        fm, _ = _parse_rendered(result)

        assert fm["due_date"] == ""
        assert fm["priority"] == "medium"

    def test_source_note_with_url(self):
        result = render_template(
            "source",
            "Great article",
            content="My notes on this",
            source_url="https://example.com/article",
        )
        fm, body = _parse_rendered(result)

        assert fm["type"] == "source"
        assert fm["source_url"] == "https://example.com/article"
        assert "## Summary" in body
        assert "## Key Points" in body
        assert "My notes on this" in body

    def test_concept_note(self):
        result = render_template(
            "concept", "Zettelkasten", content="A note-taking method"
        )
        fm, body = _parse_rendered(result)

        assert fm["type"] == "concept"
        assert "## Definition" in body
        assert "A note-taking method" in body
        assert "## Connections" in body

    def test_permanent_note(self):
        result = render_template(
            "permanent", "Key insight", tags=["philosophy"], content="Deep thought"
        )
        fm, body = _parse_rendered(result)

        assert fm["type"] == "permanent"
        assert "Deep thought" in body
        assert "## Evidence" in body
        assert "## Open Questions" in body

    def test_project_note(self):
        result = render_template("project", "Build Cortex", content="An AI second brain")
        fm, body = _parse_rendered(result)

        assert fm["type"] == "project"
        assert "## Goal" in body
        assert "An AI second brain" in body
        assert "## Resources" in body

    def test_review_note(self):
        result = render_template("review", "Week 12 Review", content="Good progress")
        fm, body = _parse_rendered(result)

        assert fm["type"] == "review"
        assert "## Summary" in body
        assert "Good progress" in body
        assert "## Next Steps" in body

    def test_default_tags_empty(self):
        result = render_template("inbox", "No tags")
        fm, _ = _parse_rendered(result)
        assert fm["tags"] == []

    def test_invalid_note_type_raises(self):
        with pytest.raises(ValueError, match="Unknown note type"):
            render_template("invalid_type", "Bad")

    def test_all_note_types_render(self):
        """Every supported note type should render without error."""
        for note_type in NOTE_TYPES:
            result = render_template(note_type, f"Test {note_type}", content="body")
            fm, body = _parse_rendered(result)
            assert fm["type"] == note_type
            assert fm["status"] == "active"
            assert "body" in body
