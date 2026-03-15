"""MCP server with capture, search, and admin tools.

Exposes Cortex capabilities as MCP tools that Claude Code can call natively.
Capture tools return draft previews — never write directly to the vault.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone

from fastmcp import FastMCP

from cortex.capture.draft import DraftManager
from cortex.capture.link import save_link
from cortex.capture.note import create_note as create_note_cmd
from cortex.capture.task import add_task
from cortex.capture.thought import capture_thought
from cortex.config import CortexConfig
from cortex.index.manager import IndexManager
from cortex.query.pipeline import QueryPipeline
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
_index: IndexManager | None = None
_last_rebuild: datetime | None = None


def init_server(
    config: CortexConfig | None = None,
    vault: VaultManager | None = None,
    drafts: DraftManager | None = None,
    index: IndexManager | None = None,
) -> FastMCP:
    """Initialize global state and return the MCP server instance.

    If arguments are None, defaults are constructed from CortexConfig().
    """
    global _config, _vault, _drafts, _index  # noqa: PLW0603

    _config = config or CortexConfig()
    _vault = vault or VaultManager(_config.vault.path, _config)
    _drafts = drafts or DraftManager(_config.draft.drafts_dir)
    _index = index

    return mcp


def _get_drafts() -> DraftManager:
    if _drafts is None:
        raise RuntimeError("Server not initialized — call init_server() first")
    return _drafts


def _get_vault() -> VaultManager:
    if _vault is None:
        raise RuntimeError("Server not initialized — call init_server() first")
    return _vault


def _get_index() -> IndexManager:
    if _index is None:
        raise RuntimeError("Index not initialized — call init_server(index=...) first")
    return _index


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


# ---------------------------------------------------------------------------
# Search tools
# ---------------------------------------------------------------------------


@mcp.tool()
def search_vault(
    query: str,
    limit: int = 10,
    note_type: str | None = None,
) -> dict:
    """Search the vault using hybrid retrieval (lexical + semantic).

    Returns structured context with ranked results. Optionally filter by note_type.
    """
    try:
        idx = _get_index()
    except RuntimeError:
        return {"error": "Index not built. Call rebuild_index() first."}

    pipeline = QueryPipeline(idx.lexical, idx.semantic)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(pipeline.execute(query, limit))

    results = result.results
    if note_type:
        results = [r for r in results if r.note_type == note_type]

    return {
        "query": result.query,
        "total": len(results),
        "explanation": result.explanation,
        "context": result.context,
        "results": [
            {
                "note_id": r.note_id,
                "title": r.title,
                "score": round(r.score, 4),
                "matched_by": r.matched_by,
                "snippet": r.snippet,
                "note_type": r.note_type,
            }
            for r in results
        ],
    }


@mcp.tool()
def get_note(note_id: str) -> dict:
    """Retrieve the full content of a note by its ID.

    Returns the note's title, type, content, tags, and metadata.
    """
    try:
        vault = _get_vault()
    except RuntimeError:
        return {"error": "Vault not initialized."}

    try:
        note = vault.get_note(note_id)
    except KeyError:
        return {"error": f"Note not found: {note_id}"}

    return {
        "note_id": note.id,
        "title": note.title,
        "note_type": note.note_type,
        "content": note.content,
        "tags": note.tags,
        "status": note.frontmatter.get("status", "active"),
        "created": note.created,
        "modified": note.modified,
        "path": str(note.path),
    }


# ---------------------------------------------------------------------------
# Admin tools
# ---------------------------------------------------------------------------


@mcp.tool()
def rebuild_index() -> dict:
    """Rebuild the full search index from the vault.

    Scans all notes and rebuilds both lexical and semantic indexes.
    This may take a while for large vaults.
    """
    global _last_rebuild  # noqa: PLW0603

    try:
        idx = _get_index()
        vault = _get_vault()
    except RuntimeError as e:
        return {"error": str(e)}

    notes = vault.scan_vault()
    idx.rebuild_all(notes)
    _last_rebuild = datetime.now(timezone.utc)

    return {
        "status": "rebuilt",
        "notes_indexed": len(notes),
        "timestamp": _last_rebuild.isoformat(),
    }


@mcp.tool()
def vault_stats() -> dict:
    """Return vault statistics: note counts by type, index sizes, last rebuild time."""
    try:
        vault = _get_vault()
    except RuntimeError:
        return {"error": "Vault not initialized."}

    notes = vault.scan_vault()

    type_counts = dict(Counter(n.note_type for n in notes))

    # Index sizes
    index_info: dict = {}
    try:
        idx = _get_index()
        try:
            row = idx.lexical._conn.execute("SELECT count(*) FROM notes").fetchone()
            index_info["lexical_notes"] = row[0] if row else 0
        except Exception:
            index_info["lexical_notes"] = 0
        try:
            tbl = idx.semantic._db.open_table("chunks")
            index_info["semantic_chunks"] = tbl.count_rows()
        except Exception:
            index_info["semantic_chunks"] = 0
    except RuntimeError:
        index_info["lexical_notes"] = 0
        index_info["semantic_chunks"] = 0

    return {
        "total_notes": len(notes),
        "by_type": type_counts,
        "index": index_info,
        "last_rebuild": _last_rebuild.isoformat() if _last_rebuild else None,
    }
