"""Tests for inbox processing workflow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from cortex.config import CortexConfig
from cortex.vault.manager import VaultManager
from cortex.workflow.inbox import InboxItem, process_inbox


@pytest.fixture
def tmp_vault(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    for folder in ("00-inbox", "01-daily", "02-tasks", "10-sources", "20-concepts", "30-permanent"):
        (vault_dir / folder).mkdir()
    return vault_dir


@pytest.fixture
def vault(tmp_vault):
    config = CortexConfig(vault={"path": str(tmp_vault)})
    return VaultManager(tmp_vault, config)


def _write_note(vault_dir: Path, folder: str, filename: str, **kwargs) -> str:
    """Write a note file and return its ID."""
    note_id = kwargs.get("note_id", str(uuid4()))
    title = kwargs.get("title", "Test Note")
    note_type = kwargs.get("note_type", "inbox")
    content = kwargs.get("content", "Some content")
    tags = kwargs.get("tags", [])
    created = kwargs.get("created", datetime.now(timezone.utc).isoformat())

    tags_yaml = "\n".join(f"  - {t}" for t in tags)
    tags_section = f"tags:\n{tags_yaml}" if tags else "tags: []"

    md = f"""---
id: {note_id}
title: {title}
type: {note_type}
created: {created}
modified: {created}
status: active
{tags_section}
---

{content}
"""
    filepath = vault_dir / folder / filename
    filepath.write_text(md, encoding="utf-8")
    return note_id


class TestProcessInbox:
    """Tests for process_inbox()."""

    def test_empty_inbox(self, vault):
        """Returns empty list when no inbox notes exist."""
        items = process_inbox(vault)
        assert items == []

    def test_lists_inbox_notes(self, tmp_vault, vault):
        """Returns InboxItem for each note in 00-inbox/."""
        id1 = _write_note(tmp_vault, "00-inbox", "note1.md", title="First thought")
        id2 = _write_note(tmp_vault, "00-inbox", "note2.md", title="Second thought")

        items = process_inbox(vault)
        assert len(items) == 2
        titles = {item.title for item in items}
        assert titles == {"First thought", "Second thought"}

    def test_ignores_non_inbox_notes(self, tmp_vault, vault):
        """Notes in other folders are not included."""
        _write_note(tmp_vault, "00-inbox", "inbox.md", title="Inbox note")
        _write_note(tmp_vault, "20-concepts", "concept.md", title="Concept", note_type="concept")

        items = process_inbox(vault)
        assert len(items) == 1
        assert items[0].title == "Inbox note"

    def test_item_has_summary(self, tmp_vault, vault):
        """InboxItem includes a content summary."""
        _write_note(tmp_vault, "00-inbox", "note.md", title="My thought", content="This is the body text of my note.")

        items = process_inbox(vault)
        assert len(items) == 1
        assert "body text" in items[0].summary

    def test_suggests_source_for_urls(self, tmp_vault, vault):
        """Notes containing URLs are suggested as source notes."""
        _write_note(tmp_vault, "00-inbox", "link.md", title="A link", content="Check out https://example.com")

        items = process_inbox(vault)
        assert items[0].suggested_type == "source"
        assert items[0].suggested_folder == "10-sources"

    def test_suggests_task_for_todos(self, tmp_vault, vault):
        """Notes containing TODO markers are suggested as tasks."""
        _write_note(tmp_vault, "00-inbox", "todo.md", title="A task", content="TODO: fix the bug")

        items = process_inbox(vault)
        assert items[0].suggested_type == "task"
        assert items[0].suggested_folder == "02-tasks"

    def test_age_in_days(self, tmp_vault, vault):
        """InboxItem.age_days reflects note age."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        _write_note(tmp_vault, "00-inbox", "old.md", title="Old note", created=old_date)

        items = process_inbox(vault)
        assert items[0].age_days >= 5

    def test_sorted_oldest_first(self, tmp_vault, vault):
        """Items are sorted by age descending (oldest first)."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        new_date = datetime.now(timezone.utc).isoformat()

        _write_note(tmp_vault, "00-inbox", "new.md", title="New", created=new_date)
        _write_note(tmp_vault, "00-inbox", "old.md", title="Old", created=old_date)

        items = process_inbox(vault)
        assert items[0].title == "Old"
        assert items[1].title == "New"

    def test_suggested_tags_from_note(self, tmp_vault, vault):
        """Suggested tags come from the note's existing tags."""
        _write_note(tmp_vault, "00-inbox", "tagged.md", title="Tagged", tags=["python", "ai"])

        items = process_inbox(vault)
        assert "python" in items[0].suggested_tags
        assert "ai" in items[0].suggested_tags


class TestMCPProcessInbox:
    """Test the MCP tool wrapper."""

    def test_mcp_tool_returns_items(self, tmp_vault):
        """The mcp_process_inbox tool returns formatted inbox items."""
        from cortex.mcp.server import init_server, mcp_process_inbox

        config = CortexConfig(vault={"path": str(tmp_vault)})
        vault = VaultManager(tmp_vault, config)
        _write_note(tmp_vault, "00-inbox", "note.md", title="Test item", content="Hello world")

        init_server(config=config, vault=vault)
        result = mcp_process_inbox()

        assert result["total"] == 1
        assert result["items"][0]["title"] == "Test item"
        assert "summary" in result["items"][0]
        assert "suggested_type" in result["items"][0]
