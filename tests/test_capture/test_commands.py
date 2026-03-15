"""Tests for capture commands: capture_thought, add_task, save_link, create_note."""

from __future__ import annotations

import pytest

from cortex.capture.draft import DraftManager
from cortex.capture.thought import capture_thought
from cortex.capture.task import add_task
from cortex.capture.link import save_link
from cortex.capture.note import create_note


@pytest.fixture
def draft_manager(tmp_path):
    """Create a DraftManager with a temp directory."""
    return DraftManager(tmp_path / "drafts")


class TestCaptureThought:
    def test_creates_inbox_draft(self, draft_manager):
        draft = capture_thought(draft_manager, "Remember to buy milk")
        assert draft.note_type == "inbox"
        assert draft.target_folder == "00-inbox"
        assert draft.content == "Remember to buy milk"
        assert draft.title == "Remember to buy milk"

    def test_with_tags(self, draft_manager):
        draft = capture_thought(draft_manager, "ML idea", tags=["ml", "research"])
        assert draft.frontmatter["tags"] == ["ml", "research"]

    def test_no_tags(self, draft_manager):
        draft = capture_thought(draft_manager, "Quick note")
        assert draft.frontmatter["tags"] == []

    def test_title_from_first_line(self, draft_manager):
        draft = capture_thought(draft_manager, "First line\nSecond line\nThird")
        assert draft.title == "First line"
        assert draft.content == "First line\nSecond line\nThird"

    def test_long_title_truncated(self, draft_manager):
        long_text = "A" * 100
        draft = capture_thought(draft_manager, long_text)
        assert len(draft.title) == 60


class TestAddTask:
    def test_creates_task_draft(self, draft_manager):
        draft = add_task(draft_manager, "Fix login bug")
        assert draft.note_type == "task"
        assert draft.target_folder == "02-tasks"
        assert draft.title == "Fix login bug"

    def test_with_all_fields(self, draft_manager):
        draft = add_task(
            draft_manager,
            "Deploy v2",
            description="Deploy the new version",
            due_date="2026-04-01",
            priority="high",
            tags=["deploy", "urgent"],
        )
        assert draft.frontmatter["due_date"] == "2026-04-01"
        assert draft.frontmatter["priority"] == "high"
        assert draft.frontmatter["tags"] == ["deploy", "urgent"]
        assert draft.content == "Deploy the new version"

    def test_no_optional_fields(self, draft_manager):
        draft = add_task(draft_manager, "Simple task")
        assert draft.content == ""
        assert draft.frontmatter["priority"] == "medium"
        assert draft.frontmatter["due_date"] == ""


class TestSaveLink:
    def test_creates_source_draft(self, draft_manager):
        draft = save_link(draft_manager, "https://example.com")
        assert draft.note_type == "source"
        assert draft.target_folder == "10-sources"
        assert draft.frontmatter["source_url"] == "https://example.com"

    def test_title_defaults_to_url(self, draft_manager):
        draft = save_link(draft_manager, "https://example.com/article")
        assert draft.title == "https://example.com/article"

    def test_with_custom_title(self, draft_manager):
        draft = save_link(
            draft_manager,
            "https://example.com",
            title="Great Article",
            description="Worth reading",
            tags=["reading"],
        )
        assert draft.title == "Great Article"
        assert draft.content == "Worth reading"
        assert draft.frontmatter["tags"] == ["reading"]


class TestCreateNote:
    def test_creates_concept_draft(self, draft_manager):
        draft = create_note(
            draft_manager, "concept", "Machine Learning", "ML is a subset of AI"
        )
        assert draft.note_type == "concept"
        assert draft.target_folder == "20-concepts"
        assert draft.title == "Machine Learning"
        assert draft.content == "ML is a subset of AI"

    def test_creates_permanent_draft(self, draft_manager):
        draft = create_note(
            draft_manager, "permanent", "Evergreen Idea", "This is important"
        )
        assert draft.note_type == "permanent"
        assert draft.target_folder == "30-permanent"

    def test_creates_project_draft(self, draft_manager):
        draft = create_note(
            draft_manager,
            "project",
            "Build Cortex",
            "AI second brain",
            tags=["project", "ai"],
        )
        assert draft.note_type == "project"
        assert draft.target_folder == "40-projects"
        assert draft.frontmatter["tags"] == ["project", "ai"]

    def test_invalid_type_raises(self, draft_manager):
        with pytest.raises(ValueError, match="Unknown note type"):
            create_note(draft_manager, "invalid", "Bad", "content")


class TestDraftPersistence:
    def test_drafts_are_persisted(self, draft_manager):
        """All capture commands persist drafts via DraftManager."""
        draft = capture_thought(draft_manager, "Persisted thought")
        loaded = draft_manager.get_draft(draft.draft_id)
        assert loaded.title == draft.title
        assert loaded.content == draft.content
