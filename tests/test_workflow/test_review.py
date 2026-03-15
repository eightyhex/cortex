"""Tests for review generation workflow."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from cortex.config import CortexConfig
from cortex.vault.manager import VaultManager
from cortex.workflow.review import ReviewDraft, generate_review


@pytest.fixture
def tmp_vault(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    for folder in (
        "00-inbox", "01-daily", "02-tasks", "10-sources",
        "20-concepts", "30-permanent", "40-projects", "50-reviews",
    ):
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
    status = kwargs.get("status", "active")
    created = kwargs.get("created", datetime.now(timezone.utc).isoformat())

    tags_yaml = "\n".join(f"  - {t}" for t in tags)
    tags_section = f"tags:\n{tags_yaml}" if tags else "tags: []"

    md = f"""---
id: {note_id}
title: {title}
type: {note_type}
created: {created}
modified: {created}
status: {status}
{tags_section}
---

{content}
"""
    filepath = vault_dir / folder / filename
    filepath.write_text(md, encoding="utf-8")
    return note_id


class TestGenerateReview:
    """Tests for generate_review()."""

    def test_empty_vault(self, vault):
        """Returns empty review when no notes exist."""
        review = generate_review(vault, period="weekly")
        assert isinstance(review, ReviewDraft)
        assert review.total_notes == 0
        assert review.counts_by_type == {}
        assert review.new_captures == []
        assert review.completed_tasks == []
        assert review.key_themes == []

    def test_weekly_counts_notes_in_period(self, tmp_vault, vault):
        """Weekly review only includes notes from the last 7 days."""
        today = date.today()
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        _write_note(tmp_vault, "00-inbox", "recent.md", title="Recent", created=recent)
        _write_note(tmp_vault, "20-concepts", "old.md", title="Old", note_type="concept", created=old)

        review = generate_review(vault, period="weekly", target_date=today)
        assert review.total_notes == 1
        assert review.period == "weekly"

    def test_monthly_includes_wider_range(self, tmp_vault, vault):
        """Monthly review includes notes from the last 30 days."""
        today = date.today()
        two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

        _write_note(tmp_vault, "20-concepts", "concept.md", title="Two weeks old",
                     note_type="concept", created=two_weeks_ago)

        review = generate_review(vault, period="monthly", target_date=today)
        assert review.total_notes == 1
        assert review.period == "monthly"

    def test_counts_by_type(self, tmp_vault, vault):
        """Review includes note counts broken down by type."""
        recent = datetime.now(timezone.utc).isoformat()
        _write_note(tmp_vault, "00-inbox", "a.md", title="A", note_type="inbox", created=recent)
        _write_note(tmp_vault, "00-inbox", "b.md", title="B", note_type="inbox", created=recent)
        _write_note(tmp_vault, "02-tasks", "c.md", title="C", note_type="task", created=recent)

        review = generate_review(vault, period="weekly")
        assert review.counts_by_type.get("inbox") == 2
        assert review.counts_by_type.get("task") == 1

    def test_new_captures_listed(self, tmp_vault, vault):
        """Inbox notes in period appear as new captures."""
        recent = datetime.now(timezone.utc).isoformat()
        _write_note(tmp_vault, "00-inbox", "thought.md", title="Quick thought",
                     note_type="inbox", created=recent)

        review = generate_review(vault, period="weekly")
        assert len(review.new_captures) == 1
        assert review.new_captures[0]["title"] == "Quick thought"

    def test_completed_tasks(self, tmp_vault, vault):
        """Tasks with status=done appear as completed tasks."""
        recent = datetime.now(timezone.utc).isoformat()
        _write_note(tmp_vault, "02-tasks", "done.md", title="Done task",
                     note_type="task", status="done", created=recent)
        _write_note(tmp_vault, "02-tasks", "active.md", title="Active task",
                     note_type="task", status="active", created=recent)

        review = generate_review(vault, period="weekly")
        assert len(review.completed_tasks) == 1
        assert review.completed_tasks[0]["title"] == "Done task"

    def test_active_projects_from_full_vault(self, tmp_vault, vault):
        """Active projects include all active projects, not just period ones."""
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        _write_note(tmp_vault, "40-projects", "proj.md", title="My Project",
                     note_type="project", status="active", created=old)

        review = generate_review(vault, period="weekly")
        assert len(review.active_projects) == 1
        assert review.active_projects[0]["title"] == "My Project"

    def test_key_themes_from_tags(self, tmp_vault, vault):
        """Key themes are extracted from note tags in the period."""
        recent = datetime.now(timezone.utc).isoformat()
        _write_note(tmp_vault, "00-inbox", "a.md", title="A",
                     tags=["python", "ai"], created=recent)
        _write_note(tmp_vault, "00-inbox", "b.md", title="B",
                     tags=["python", "data"], created=recent)

        review = generate_review(vault, period="weekly")
        assert "python" in review.key_themes
        # python should be first (most common)
        assert review.key_themes[0] == "python"


class TestMCPGenerateReview:
    """Test the MCP tool wrapper."""

    def test_mcp_tool_returns_review(self, tmp_vault):
        """The mcp_generate_review tool returns review data."""
        from cortex.mcp.server import init_server, mcp_generate_review

        config = CortexConfig(vault={"path": str(tmp_vault)})
        vault_mgr = VaultManager(tmp_vault, config)
        recent = datetime.now(timezone.utc).isoformat()
        _write_note(tmp_vault, "00-inbox", "note.md", title="Test",
                     note_type="inbox", created=recent)

        init_server(config=config, vault=vault_mgr)
        result = mcp_generate_review(period="weekly")

        assert result["period"] == "weekly"
        assert result["total_notes"] == 1
        assert "counts_by_type" in result
        assert "new_captures" in result
        assert "key_themes" in result
