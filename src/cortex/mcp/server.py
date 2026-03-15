"""MCP server with capture and draft lifecycle tools.

Exposes Cortex capabilities as MCP tools that Claude Code can call natively.
Capture tools return draft previews — never write directly to the vault.
"""

from __future__ import annotations

from fastmcp import FastMCP

from cortex.capture.draft import DraftManager
from cortex.capture.link import save_link
from cortex.capture.note import create_note as create_note_cmd
from cortex.capture.task import add_task
from cortex.capture.thought import capture_thought
from cortex.config import CortexConfig
from cortex.vault.manager import VaultManager

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP("cortex", instructions="Cortex — local-first AI-native second brain")

# ---------------------------------------------------------------------------
# Shared state (initialized in init_server)
# ---------------------------------------------------------------------------

_config: CortexConfig | None = None
_vault: VaultManager | None = None
_drafts: DraftManager | None = None


def init_server(
    config: CortexConfig | None = None,
    vault: VaultManager | None = None,
    drafts: DraftManager | None = None,
) -> FastMCP:
    """Initialize global state and return the MCP server instance.

    If arguments are None, defaults are constructed from CortexConfig().
    """
    global _config, _vault, _drafts  # noqa: PLW0603

    _config = config or CortexConfig()
    _vault = vault or VaultManager(_config.vault.path, _config)
    _drafts = drafts or DraftManager(_config.draft.drafts_dir)

    return mcp


def _get_drafts() -> DraftManager:
    if _drafts is None:
        raise RuntimeError("Server not initialized — call init_server() first")
    return _drafts


def _get_vault() -> VaultManager:
    if _vault is None:
        raise RuntimeError("Server not initialized — call init_server() first")
    return _vault


def _draft_response(draft) -> dict:
    """Standard response for capture tools."""
    return {
        "draft_id": draft.draft_id,
        "preview": draft.render_preview(),
        "target_folder": draft.target_folder,
        "target_filename": draft.target_filename,
    }


# ---------------------------------------------------------------------------
# Capture tools
# ---------------------------------------------------------------------------


@mcp.tool()
def mcp_capture_thought(
    content: str,
    tags: list[str] | None = None,
) -> dict:
    """Capture a quick thought as an inbox note.

    Creates a draft note — ALWAYS show the returned preview to the user
    and ask for their approval before calling approve_draft.
    """
    draft = capture_thought(_get_drafts(), content, tags)
    return _draft_response(draft)


@mcp.tool()
def mcp_add_task(
    title: str,
    description: str | None = None,
    due_date: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Create a task note.

    Creates a draft note — ALWAYS show the returned preview to the user
    and ask for their approval before calling approve_draft.
    """
    draft = add_task(_get_drafts(), title, description, due_date, priority, tags)
    return _draft_response(draft)


@mcp.tool()
def mcp_save_link(
    url: str,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Save a web link as a source note.

    Creates a draft note — ALWAYS show the returned preview to the user
    and ask for their approval before calling approve_draft.
    """
    draft = save_link(_get_drafts(), url, title, description, tags)
    return _draft_response(draft)


@mcp.tool()
def mcp_create_note(
    note_type: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
) -> dict:
    """Create a note of any type (concept, permanent, project, etc.).

    Creates a draft note — ALWAYS show the returned preview to the user
    and ask for their approval before calling approve_draft.
    """
    draft = create_note_cmd(_get_drafts(), note_type, title, content, tags)
    return _draft_response(draft)


# ---------------------------------------------------------------------------
# Draft lifecycle tools
# ---------------------------------------------------------------------------


@mcp.tool()
def approve_draft(draft_id: str) -> dict:
    """Approve a draft and write it to the vault.

    Only call this after showing the preview to the user and receiving
    explicit approval. Returns the created note's ID and path.
    """
    note = _get_drafts().approve_draft(draft_id, _get_vault())
    return {
        "note_id": note.id,
        "path": str(note.path),
    }


@mcp.tool()
def update_draft(draft_id: str, edits: dict) -> dict:
    """Update a pending draft with user-requested changes.

    Supported edits: title, content, tags, folder.
    Returns the updated preview so you can show it to the user again.
    """
    draft = _get_drafts().update_draft(draft_id, edits)
    return _draft_response(draft)


@mcp.tool()
def reject_draft(draft_id: str) -> dict:
    """Discard a draft. The note will not be saved to the vault."""
    _get_drafts().reject_draft(draft_id)
    return {"status": "rejected", "draft_id": draft_id}
