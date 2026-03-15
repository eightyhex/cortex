"""Tests for link & tag extraction from note content."""

from pathlib import Path

import pytest

from cortex.vault.parser import (
    Link,
    extract_inline_tags,
    extract_markdown_links,
    extract_wikilinks,
    parse_note,
)


def _write_note(vault: Path, filename: str, content: str) -> Path:
    p = vault / filename
    p.write_text(content, encoding="utf-8")
    return p


class TestExtractWikilinks:
    def test_simple_wikilinks(self) -> None:
        content = "See [[Python]] and [[Rust]] for details."
        assert extract_wikilinks(content) == ["Python", "Rust"]

    def test_aliased_wikilinks(self) -> None:
        content = "Check [[Python|the Python language]] and [[Rust|Rust lang]]."
        assert extract_wikilinks(content) == ["Python", "Rust"]

    def test_no_wikilinks(self) -> None:
        assert extract_wikilinks("No links here.") == []

    def test_mixed_wikilinks(self) -> None:
        content = "See [[Simple]], [[Aliased|with alias]], and [[Another]]."
        assert extract_wikilinks(content) == ["Simple", "Aliased", "Another"]


class TestExtractMarkdownLinks:
    def test_markdown_links(self) -> None:
        content = "Read [this article](https://example.com) and [docs](https://docs.io)."
        result = extract_markdown_links(content)
        assert result == [("this article", "https://example.com"), ("docs", "https://docs.io")]

    def test_no_markdown_links(self) -> None:
        assert extract_markdown_links("No links here.") == []


class TestExtractInlineTags:
    def test_simple_tags(self) -> None:
        content = "This is about #python and #testing."
        assert extract_inline_tags(content) == ["python", "testing"]

    def test_tags_at_start_of_line(self) -> None:
        content = "#firsttag is at the start\nand #secondtag here."
        assert extract_inline_tags(content) == ["firsttag", "secondtag"]

    def test_no_tags(self) -> None:
        assert extract_inline_tags("No tags here.") == []

    def test_tags_in_code_blocks_excluded(self) -> None:
        content = """\
This has #realtag outside code.

```python
# This is a comment with #faketag
print("#notarealtag")
```

And `#inlinecode` should be excluded too.

But #anothertag is real.
"""
        tags = extract_inline_tags(content)
        assert "realtag" in tags
        assert "anothertag" in tags
        assert "faketag" not in tags
        assert "notarealtag" not in tags
        assert "inlinecode" not in tags

    def test_tags_with_hyphens_and_slashes(self) -> None:
        content = "Tags: #machine-learning #ai/ml"
        tags = extract_inline_tags(content)
        assert "machine-learning" in tags
        assert "ai/ml" in tags

    def test_number_only_not_tag(self) -> None:
        # #123 should not be a tag (starts with digit)
        content = "Issue #123 is not a tag but #valid is."
        tags = extract_inline_tags(content)
        assert "123" not in tags
        assert "valid" in tags


class TestParseNoteLinks:
    def test_parse_note_populates_links(self, tmp_path: Path) -> None:
        path = _write_note(
            tmp_path,
            "linked.md",
            """\
---
id: "note-1"
title: "Linked Note"
type: concept
tags:
  - existing
---

See [[Python]] and [[Rust]] for details.
""",
        )
        note = parse_note(path)

        assert len(note.links) == 2
        assert isinstance(note.links[0], Link)
        assert note.links[0].source_id == "note-1"
        assert note.links[0].target_id == "Python"
        assert note.links[0].link_type == "wikilink"
        assert note.links[1].target_id == "Rust"

    def test_parse_note_merges_tags(self, tmp_path: Path) -> None:
        path = _write_note(
            tmp_path,
            "tagged.md",
            """\
---
id: "note-2"
title: "Tagged Note"
type: concept
tags:
  - python
  - testing
---

Also about #machinelearning and #python (duplicate).
""",
        )
        note = parse_note(path)

        # python from frontmatter, testing from frontmatter, machinelearning from inline
        assert "python" in note.tags
        assert "testing" in note.tags
        assert "machinelearning" in note.tags
        # No duplicates
        assert note.tags.count("python") == 1

    def test_parse_note_no_links(self, tmp_path: Path) -> None:
        path = _write_note(
            tmp_path,
            "nolinks.md",
            """\
---
id: "note-3"
title: "No Links"
type: inbox
---

Just plain text, no links here.
""",
        )
        note = parse_note(path)
        assert note.links == []

    def test_mixed_content(self, tmp_path: Path) -> None:
        path = _write_note(
            tmp_path,
            "mixed.md",
            """\
---
id: "note-4"
title: "Mixed Content"
type: concept
tags:
  - original
---

Links to [[Concept A]] and [[Concept B|alias B]].
Also see [external](https://example.com).
Tags: #newtag and #original (already in frontmatter).

```python
# [[not a link]] and #notarealtag
```
""",
        )
        note = parse_note(path)

        # Wikilinks extracted (including from code blocks - regex is simple)
        wikilink_targets = [link.target_id for link in note.links]
        assert "Concept A" in wikilink_targets
        assert "Concept B" in wikilink_targets

        # Tags merged and deduplicated
        assert "original" in note.tags
        assert "newtag" in note.tags
        assert note.tags.count("original") == 1
