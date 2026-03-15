"""Tests for NoteDraft and DraftManager."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml

from cortex.capture.draft import DraftManager, NoteDraft, _STALE_THRESHOLD_SECS


@pytest.fixture
def drafts_dir(tmp_path: Path) -> Path:
    """Temporary directory for draft files."""
    d = tmp_path / "drafts"
    d.mkdir()
    return d


@pytest.fixture
def manager(drafts_dir: Path) -> DraftManager:
    return DraftManager(drafts_dir)


class TestNoteDraft:
    """Tests for the NoteDraft dataclass."""

    def test_render_preview_contains_key_fields(self, manager: DraftManager) -> None:
        draft = manager.create_draft(
            note_type="inbox",
            title="Test Thought",
            content="Some content here",
            metadata={"tags": ["idea", "test"]},
        )
        preview = draft.render_preview()
        assert "Test Thought" in preview
        assert "inbox" in preview.lower()
        assert "#idea" in preview
        assert "#test" in preview
        assert draft.target_folder in preview
        assert draft.target_filename in preview

    def test_render_markdown_valid_frontmatter(self, manager: DraftManager) -> None:
        draft = manager.create_draft(
            note_type="concept",
            title="Machine Learning",
            content="ML is a subset of AI.",
            metadata={"tags": ["ml"]},
        )
        md = draft.render_markdown()
        assert md.startswith("---\n")
        # Parse frontmatter back
        parts = md.split("---\n", 2)
        assert len(parts) == 3
        fm = yaml.safe_load(parts[1])
        assert fm["title"] == "Machine Learning"
        assert fm["type"] == "concept"
        assert "ml" in fm["tags"]
        # Body content present
        assert "ML is a subset of AI." in parts[2]

    def test_apply_edits_title(self, manager: DraftManager) -> None:
        draft = manager.create_draft("inbox", "Old Title", "content")
        edited = draft.apply_edits({"title": "New Title"})
        assert edited.title == "New Title"
        assert edited.frontmatter["title"] == "New Title"
        assert "new-title" in edited.target_filename
        # Original unchanged
        assert draft.title == "Old Title"

    def test_apply_edits_tags(self, manager: DraftManager) -> None:
        draft = manager.create_draft("inbox", "Note", "content", {"tags": ["old"]})
        edited = draft.apply_edits({"tags": ["new", "updated"]})
        assert edited.frontmatter["tags"] == ["new", "updated"]
        assert draft.frontmatter["tags"] == ["old"]

    def test_apply_edits_content(self, manager: DraftManager) -> None:
        draft = manager.create_draft("inbox", "Note", "old content")
        edited = draft.apply_edits({"content": "new content"})
        assert edited.content == "new content"
        assert draft.content == "old content"

    def test_apply_edits_folder(self, manager: DraftManager) -> None:
        draft = manager.create_draft("inbox", "Note", "content")
        edited = draft.apply_edits({"folder": "20-concepts"})
        assert edited.target_folder == "20-concepts"

    def test_render_preview_no_tags(self, manager: DraftManager) -> None:
        draft = manager.create_draft("inbox", "No Tags", "content")
        preview = draft.render_preview()
        assert "(none)" in preview


class TestDraftManager:
    """Tests for DraftManager lifecycle operations."""

    def test_create_draft_returns_valid_draft(self, manager: DraftManager) -> None:
        draft = manager.create_draft("inbox", "My Thought", "thinking about things")
        assert draft.note_type == "inbox"
        assert draft.title == "My Thought"
        assert draft.content == "thinking about things"
        assert draft.target_folder == "00-inbox"
        assert draft.target_filename.endswith(".md")
        assert "inbox" in draft.target_filename
        assert draft.frontmatter["id"]  # has a note UUID
        assert draft.frontmatter["status"] == "active"

    def test_create_draft_task_type(self, manager: DraftManager) -> None:
        draft = manager.create_draft(
            "task", "Fix Bug", "Fix the login bug",
            metadata={"due_date": "2026-04-01", "priority": "high", "tags": ["bug"]},
        )
        assert draft.frontmatter["due_date"] == "2026-04-01"
        assert draft.frontmatter["priority"] == "high"
        assert draft.target_folder == "02-tasks"

    def test_create_draft_source_type(self, manager: DraftManager) -> None:
        draft = manager.create_draft(
            "source", "Good Article", "Notes on article",
            metadata={"source_url": "https://example.com/article"},
        )
        assert draft.frontmatter["source_url"] == "https://example.com/article"
        assert draft.target_folder == "10-sources"

    def test_create_draft_invalid_type(self, manager: DraftManager) -> None:
        with pytest.raises(ValueError, match="Unknown note type"):
            manager.create_draft("invalid", "Title", "content")

    def test_get_draft_round_trip(self, manager: DraftManager) -> None:
        """Create a draft, then retrieve it by ID — JSON round-trip."""
        draft = manager.create_draft("inbox", "Round Trip", "test content", {"tags": ["test"]})
        loaded = manager.get_draft(draft.draft_id)
        assert loaded.draft_id == draft.draft_id
        assert loaded.title == draft.title
        assert loaded.content == draft.content
        assert loaded.frontmatter["tags"] == ["test"]
        assert loaded.target_folder == draft.target_folder
        assert loaded.target_filename == draft.target_filename

    def test_get_draft_not_found(self, manager: DraftManager) -> None:
        with pytest.raises(KeyError, match="Draft not found"):
            manager.get_draft("nonexistent-id")

    def test_update_draft_persists(self, manager: DraftManager) -> None:
        draft = manager.create_draft("inbox", "Original", "content")
        updated = manager.update_draft(draft.draft_id, {"title": "Updated"})
        assert updated.title == "Updated"
        # Verify persistence
        reloaded = manager.get_draft(draft.draft_id)
        assert reloaded.title == "Updated"

    def test_reject_draft_deletes_file(self, manager: DraftManager, drafts_dir: Path) -> None:
        draft = manager.create_draft("inbox", "To Reject", "content")
        draft_path = drafts_dir / f"{draft.draft_id}.json"
        assert draft_path.exists()
        manager.reject_draft(draft.draft_id)
        assert not draft_path.exists()

    def test_reject_nonexistent_draft_no_error(self, manager: DraftManager) -> None:
        """Rejecting a draft that doesn't exist should not raise."""
        manager.reject_draft("nonexistent-id")  # no error

    def test_cleanup_stale_drafts(self, drafts_dir: Path) -> None:
        """Drafts older than 24 hours are cleaned up on init."""
        # Create a "stale" draft file with old mtime
        stale_file = drafts_dir / "stale-draft.json"
        stale_file.write_text(json.dumps({"draft_id": "stale"}))
        import os
        old_time = time.time() - _STALE_THRESHOLD_SECS - 100
        os.utime(stale_file, (old_time, old_time))

        # Create a "fresh" draft file
        fresh_file = drafts_dir / "fresh-draft.json"
        fresh_file.write_text(json.dumps({"draft_id": "fresh"}))

        # Init manager triggers cleanup
        DraftManager(drafts_dir)

        assert not stale_file.exists(), "Stale draft should be deleted"
        assert fresh_file.exists(), "Fresh draft should be kept"

    def test_file_naming_format(self, manager: DraftManager) -> None:
        """Filename follows {date}-{type}-{short-hash}-{slug}.md pattern."""
        draft = manager.create_draft("concept", "My Great Idea", "content")
        fn = draft.target_filename
        # Should match pattern: YYYY-MM-DD-concept-XXXX-my-great-idea.md
        assert fn.endswith(".md")
        parts = fn.removesuffix(".md").split("-", 4)  # date parts + type start
        assert len(parts) >= 5  # YYYY, MM, DD, concept, rest
        assert parts[3] == "concept"

    def test_creates_drafts_dir_if_missing(self, tmp_path: Path) -> None:
        """DraftManager creates the drafts directory if it doesn't exist."""
        new_dir = tmp_path / "new" / "drafts"
        assert not new_dir.exists()
        mgr = DraftManager(new_dir)
        assert new_dir.is_dir()

    def test_all_note_types_have_correct_folders(self, manager: DraftManager) -> None:
        """Each note type maps to the correct vault folder."""
        expected = {
            "inbox": "00-inbox",
            "daily": "01-daily",
            "task": "02-tasks",
            "source": "10-sources",
            "concept": "20-concepts",
            "permanent": "30-permanent",
            "project": "40-projects",
            "review": "50-reviews",
        }
        for note_type, folder in expected.items():
            draft = manager.create_draft(note_type, f"Test {note_type}", "content")
            assert draft.target_folder == folder, f"{note_type} should map to {folder}"
