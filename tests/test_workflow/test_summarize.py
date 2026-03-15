"""Tests for source summarization workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from cortex.config import CortexConfig
from cortex.vault.manager import VaultManager
from cortex.workflow.summarize import summarize_source


@pytest.fixture
def tmp_vault(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    for folder in ("00-inbox", "10-sources", "20-concepts"):
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
    note_type = kwargs.get("note_type", "source")
    content = kwargs.get("content", "Some content")
    tags = kwargs.get("tags", [])
    source_url = kwargs.get("source_url", "")
    created = kwargs.get("created", datetime.now(timezone.utc).isoformat())

    tags_yaml = "\n".join(f"  - {t}" for t in tags)
    tags_section = f"tags:\n{tags_yaml}" if tags else "tags: []"
    source_line = f"source_url: {source_url}" if source_url else ""

    md = f"""---
id: {note_id}
title: {title}
type: {note_type}
created: {created}
modified: {created}
status: active
{tags_section}
{source_line}
---

{content}
"""
    filepath = vault_dir / folder / filename
    filepath.write_text(md, encoding="utf-8")
    return note_id


class TestSummarizeSource:
    """Tests for summarize_source()."""

    def test_basic_summarization(self, tmp_vault, vault):
        """Returns dict with expected keys for a source note."""
        note_id = _write_note(
            tmp_vault, "10-sources", "article.md",
            title="Python Tips",
            content="## Introduction\n\nSome tips about Python.\n\n## Advanced\n\nMore content here.",
            source_url="https://example.com/python-tips",
            tags=["python", "tips"],
        )

        note = vault.get_note(note_id)
        result = summarize_source(note)

        assert result["note_id"] == note_id
        assert result["title"] == "Python Tips"
        assert result["note_type"] == "source"
        assert result["source_url"] == "https://example.com/python-tips"
        assert "python" in result["tags"]
        assert "Introduction" in result["headings"]
        assert "Advanced" in result["headings"]
        assert result["word_count"] > 0
        assert "content_excerpt" in result
        assert result["status"] == "active"

    def test_extracts_urls_from_content(self, tmp_vault, vault):
        """Extracts URLs from both markdown links and bare URLs."""
        note_id = _write_note(
            tmp_vault, "10-sources", "links.md",
            title="Link Collection",
            content="Check [this](https://example.com) and also https://other.com/page",
        )

        note = vault.get_note(note_id)
        result = summarize_source(note)

        assert "https://example.com" in result["urls"]
        assert "https://other.com/page" in result["urls"]

    def test_truncates_long_content(self, tmp_vault, vault):
        """Content excerpt is truncated for long notes."""
        long_content = "word " * 200  # ~1000 chars
        note_id = _write_note(
            tmp_vault, "10-sources", "long.md",
            title="Long Note",
            content=long_content,
        )

        note = vault.get_note(note_id)
        result = summarize_source(note)

        assert len(result["content_excerpt"]) <= 510  # 500 + some tolerance for word boundary

    def test_empty_content(self, tmp_vault, vault):
        """Handles notes with empty content gracefully."""
        note_id = _write_note(
            tmp_vault, "10-sources", "empty.md",
            title="Empty Source",
            content="",
        )

        note = vault.get_note(note_id)
        result = summarize_source(note)

        assert result["word_count"] == 0
        assert result["headings"] == []
        assert result["urls"] == []


class TestMCPSummarizeSource:
    """Test the MCP tool wrapper."""

    def test_mcp_tool_returns_summary(self, tmp_vault):
        """The mcp_summarize_source tool returns structured summary."""
        from cortex.mcp.server import init_server, mcp_summarize_source

        config = CortexConfig(vault={"path": str(tmp_vault)})
        v = VaultManager(tmp_vault, config)
        note_id = _write_note(
            tmp_vault, "10-sources", "test.md",
            title="Test Source",
            content="## Overview\n\nA test source note.",
            source_url="https://example.com",
        )

        init_server(config=config, vault=v)
        result = mcp_summarize_source(note_id)

        assert result["title"] == "Test Source"
        assert "Overview" in result["headings"]
        assert result["source_url"] == "https://example.com"

    def test_mcp_tool_not_found(self, tmp_vault):
        """Returns error for nonexistent note ID."""
        from cortex.mcp.server import init_server, mcp_summarize_source

        config = CortexConfig(vault={"path": str(tmp_vault)})
        v = VaultManager(tmp_vault, config)
        init_server(config=config, vault=v)

        result = mcp_summarize_source("nonexistent-id")
        assert "error" in result
