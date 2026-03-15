"""Tests for the MCP server tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.capture.draft import DraftManager
from cortex.config import CortexConfig
from cortex.mcp.server import (
    approve_draft,
    init_server,
    mcp,
    mcp_add_task,
    mcp_capture_thought,
    mcp_create_note,
    mcp_save_link,
    reject_draft,
    update_draft,
)
from cortex.vault.manager import VaultManager, scaffold_vault


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    scaffold_vault(vault)
    return vault


@pytest.fixture()
def config(tmp_path: Path, vault_dir: Path) -> CortexConfig:
    return CortexConfig(
        vault={"path": str(vault_dir)},
        draft={"drafts_dir": str(tmp_path / "drafts")},
        index={"db_path": str(tmp_path / "cortex.duckdb"), "embeddings_path": str(tmp_path / "embeddings")},
    )


@pytest.fixture()
def server(config: CortexConfig, vault_dir: Path):
    vault = VaultManager(vault_dir, config)
    drafts = DraftManager(config.draft.drafts_dir)
    return init_server(config=config, vault=vault, drafts=drafts)


# ---------------------------------------------------------------------------
# Capture tools
# ---------------------------------------------------------------------------


class TestCaptureThought:
    def test_returns_draft_response(self, server):
        result = mcp_capture_thought(content="Test thought")
        assert "draft_id" in result
        assert "preview" in result
        assert "target_folder" in result
        assert "target_filename" in result

    def test_preview_contains_content(self, server):
        result = mcp_capture_thought(content="My important idea")
        assert "My important idea" in result["preview"]

    def test_target_folder_is_inbox(self, server):
        result = mcp_capture_thought(content="Quick note")
        assert result["target_folder"] == "00-inbox"

    def test_with_tags(self, server):
        result = mcp_capture_thought(content="Tagged thought", tags=["idea", "test"])
        assert "#idea" in result["preview"]
        assert "#test" in result["preview"]


class TestAddTask:
    def test_returns_draft_response(self, server):
        result = mcp_add_task(title="Do something")
        assert "draft_id" in result
        assert result["target_folder"] == "02-tasks"

    def test_with_all_fields(self, server):
        result = mcp_add_task(
            title="Important task",
            description="Details here",
            due_date="2026-04-01",
            priority="high",
            tags=["urgent"],
        )
        assert "Important task" in result["preview"]


class TestSaveLink:
    def test_returns_draft_response(self, server):
        result = mcp_save_link(url="https://example.com")
        assert "draft_id" in result
        assert result["target_folder"] == "10-sources"

    def test_uses_url_as_default_title(self, server):
        result = mcp_save_link(url="https://example.com")
        assert "https://example.com" in result["preview"]


class TestCreateNote:
    def test_concept_note(self, server):
        result = mcp_create_note(
            note_type="concept", title="Test Concept", content="A concept."
        )
        assert result["target_folder"] == "20-concepts"

    def test_permanent_note(self, server):
        result = mcp_create_note(
            note_type="permanent", title="Insight", content="Body"
        )
        assert result["target_folder"] == "30-permanent"


# ---------------------------------------------------------------------------
# Draft lifecycle tools
# ---------------------------------------------------------------------------


class TestApproveDraft:
    def test_approve_creates_note(self, server, vault_dir: Path):
        result = mcp_capture_thought(content="Approve me")
        draft_id = result["draft_id"]

        approved = approve_draft(draft_id)
        assert "note_id" in approved
        assert "path" in approved

        # File should exist in vault
        note_path = vault_dir / approved["path"]
        assert note_path.exists()

    def test_approve_removes_draft(self, server, config: CortexConfig):
        result = mcp_capture_thought(content="Will be approved")
        draft_id = result["draft_id"]

        approve_draft(draft_id)

        # Draft file should be gone
        draft_path = config.draft.drafts_dir / f"{draft_id}.json"
        assert not draft_path.exists()


class TestUpdateDraft:
    def test_update_returns_new_preview(self, server):
        result = mcp_capture_thought(content="Original")
        draft_id = result["draft_id"]

        updated = update_draft(draft_id, {"tags": ["updated-tag"]})
        assert "#updated-tag" in updated["preview"]
        assert updated["draft_id"] == draft_id

    def test_update_title(self, server):
        result = mcp_capture_thought(content="Original")
        draft_id = result["draft_id"]

        updated = update_draft(draft_id, {"title": "New Title"})
        assert "New Title" in updated["preview"]


class TestRejectDraft:
    def test_reject_removes_draft(self, server, config: CortexConfig):
        result = mcp_capture_thought(content="Will be rejected")
        draft_id = result["draft_id"]

        rejected = reject_draft(draft_id)
        assert rejected["status"] == "rejected"
        assert rejected["draft_id"] == draft_id

        # Draft file should be gone
        draft_path = config.draft.drafts_dir / f"{draft_id}.json"
        assert not draft_path.exists()


# ---------------------------------------------------------------------------
# Tool descriptions
# ---------------------------------------------------------------------------


class TestToolDescriptions:
    """Verify that capture tool descriptions instruct Claude to show preview and ask for approval."""

    def test_capture_tools_have_approval_instructions(self, server):
        tool_functions = [mcp_capture_thought, mcp_add_task, mcp_save_link, mcp_create_note]
        for fn in tool_functions:
            doc = fn.__doc__ or ""
            assert "preview" in doc.lower(), f"{fn.__name__} missing preview instruction"
            assert "approv" in doc.lower(), f"{fn.__name__} missing approval instruction"


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------


class TestServerSetup:
    def test_mcp_instance_exists(self, server):
        assert mcp is not None
        assert mcp.name == "cortex"

    def test_init_server_returns_mcp(self, server):
        assert server is mcp
