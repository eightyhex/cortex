"""Tests for the frontmatter parser module."""

from datetime import datetime
from pathlib import Path

import pytest

from cortex.vault.parser import Note, parse_note


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    return tmp_path


def _write_note(vault: Path, filename: str, content: str) -> Path:
    p = vault / filename
    p.write_text(content, encoding="utf-8")
    return p


class TestParseNote:
    def test_valid_note(self, tmp_vault: Path) -> None:
        path = _write_note(
            tmp_vault,
            "test.md",
            """\
---
id: "abc-123"
title: "My Test Note"
type: concept
created: "2026-03-10T10:00:00"
modified: "2026-03-10T12:00:00"
tags:
  - python
  - testing
status: active
---

This is the body content.
""",
        )
        note = parse_note(path)

        assert note.id == "abc-123"
        assert note.title == "My Test Note"
        assert note.note_type == "concept"
        assert note.path == path
        assert "This is the body content." in note.content
        assert note.tags == ["python", "testing"]
        assert note.status == "active"
        assert note.created == datetime(2026, 3, 10, 10, 0, 0)
        assert note.modified == datetime(2026, 3, 10, 12, 0, 0)
        assert note.frontmatter["id"] == "abc-123"

    def test_missing_frontmatter(self, tmp_vault: Path) -> None:
        path = _write_note(tmp_vault, "no-fm.md", "Just plain markdown content.\n")
        note = parse_note(path)

        assert note.title == "no-fm"
        assert note.note_type == "inbox"
        assert note.content == "Just plain markdown content."
        assert note.tags == []
        assert note.status == "active"
        assert isinstance(note.id, str) and len(note.id) > 0

    def test_missing_fields(self, tmp_vault: Path) -> None:
        path = _write_note(
            tmp_vault,
            "partial.md",
            """\
---
title: "Partial Note"
---

Some content here.
""",
        )
        note = parse_note(path)

        assert note.title == "Partial Note"
        assert note.note_type == "inbox"  # default
        assert note.status == "active"  # default
        assert note.tags == []  # default
        assert note.supersedes is None
        assert note.superseded_by is None
        assert isinstance(note.created, datetime)
        assert isinstance(note.modified, datetime)

    def test_empty_file(self, tmp_vault: Path) -> None:
        path = _write_note(tmp_vault, "empty.md", "")
        note = parse_note(path)

        assert note.title == "empty"
        assert note.note_type == "inbox"
        assert note.content == ""
        assert note.tags == []
        assert note.status == "active"
        assert note.frontmatter == {}

    def test_all_note_types(self, tmp_vault: Path) -> None:
        note_types = [
            "inbox",
            "daily",
            "task",
            "source",
            "concept",
            "permanent",
            "project",
            "review",
        ]
        for ntype in note_types:
            path = _write_note(
                tmp_vault,
                f"{ntype}.md",
                f"---\nid: '{ntype}-1'\ntitle: '{ntype} note'\ntype: {ntype}\n---\n\nContent for {ntype}.\n",
            )
            note = parse_note(path)
            assert note.note_type == ntype, f"Failed for type: {ntype}"
            assert note.title == f"{ntype} note"

    def test_unicode_content(self, tmp_vault: Path) -> None:
        path = _write_note(
            tmp_vault,
            "unicode.md",
            """\
---
id: "uni-1"
title: "日本語のノート"
type: concept
tags:
  - 日本語
  - テスト
---

これはユニコードのテストです。Ñoño. Ümlauts. 中文测试。
""",
        )
        note = parse_note(path)

        assert note.title == "日本語のノート"
        assert "日本語" in note.tags
        assert "これはユニコードのテストです" in note.content
        assert "Ñoño" in note.content

    def test_task_specific_fields(self, tmp_vault: Path) -> None:
        path = _write_note(
            tmp_vault,
            "task.md",
            """\
---
id: "task-1"
title: "Fix the bug"
type: task
due_date: "2026-03-20"
priority: high
status: active
tags:
  - bugfix
---

Fix the critical bug in parser.
""",
        )
        note = parse_note(path)

        assert note.note_type == "task"
        assert note.frontmatter["due_date"] == "2026-03-20"
        assert note.frontmatter["priority"] == "high"

    def test_source_specific_fields(self, tmp_vault: Path) -> None:
        path = _write_note(
            tmp_vault,
            "source.md",
            """\
---
id: "src-1"
title: "Great Article"
type: source
source_url: "https://example.com/article"
tags:
  - reading
---

Summary of the article.
""",
        )
        note = parse_note(path)

        assert note.note_type == "source"
        assert note.frontmatter["source_url"] == "https://example.com/article"

    def test_supersession_fields(self, tmp_vault: Path) -> None:
        path = _write_note(
            tmp_vault,
            "superseded.md",
            """\
---
id: "old-1"
title: "Old Note"
type: concept
status: superseded
supersedes: "older-1"
superseded_by: "new-1"
---

This note has been superseded.
""",
        )
        note = parse_note(path)

        assert note.status == "superseded"
        assert note.supersedes == "older-1"
        assert note.superseded_by == "new-1"
