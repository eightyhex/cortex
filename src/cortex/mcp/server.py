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
from cortex.graph.manager import GraphManager
from cortex.health import health_check as _health_check
from cortex.index.manager import IndexManager
from cortex.lifecycle.manager import LifecycleManager
from cortex.lifecycle.staleness import detect_stale_notes
from cortex.query.pipeline import QueryPipeline
from cortex.vault.manager import VaultManager
from cortex.workflow.inbox import process_inbox as _process_inbox
from cortex.workflow.review import generate_review as _generate_review
from cortex.workflow.staleness_review import staleness_review as _staleness_review
from cortex.workflow.summarize import summarize_source as _summarize_source

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
_graph: GraphManager | None = None
_lifecycle: LifecycleManager | None = None
_last_rebuild: datetime | None = None


def init_server(
    config: CortexConfig | None = None,
    vault: VaultManager | None = None,
    drafts: DraftManager | None = None,
    index: IndexManager | None = None,
    graph: GraphManager | None = None,
) -> FastMCP:
    """Initialize global state and return the MCP server instance.

    If arguments are None, defaults are constructed from CortexConfig().
    """
    global _config, _vault, _drafts, _index, _graph, _lifecycle  # noqa: PLW0603

    _config = config or CortexConfig()
    _vault = vault or VaultManager(_config.vault.path, _config)
    _drafts = drafts or DraftManager(_config.draft.drafts_dir)
    _index = index
    _graph = graph

    # Initialize lifecycle manager if all dependencies are available
    if _index is not None and _graph is not None:
        _lifecycle = LifecycleManager(_vault, _index, _graph, _drafts)
    else:
        _lifecycle = None

    return mcp


def _get_drafts() -> DraftManager:
    if _drafts is None:
        raise RuntimeError("Server not initialized — call init_server() first")
    return _drafts


def _get_vault() -> VaultManager:
    if _vault is None:
        raise RuntimeError(
            "Vault not available. Check that the vault path exists and is readable. "
            "If running in Docker, verify the volume mount (e.g., -v /path/to/vault:/app/vault)."
        )
    return _vault


def _get_index() -> IndexManager:
    if _index is None:
        raise RuntimeError(
            "Search index not available. "
            "Ensure Cortex was started with index support enabled (see main.py)."
        )
    return _index


def _get_lifecycle() -> LifecycleManager:
    if _lifecycle is None:
        raise RuntimeError(
            "Lifecycle not initialized — call init_server(index=..., graph=...) first"
        )
    return _lifecycle


def _get_graph() -> GraphManager:
    if _graph is None:
        raise RuntimeError("Graph not initialized — call init_server(graph=...) first")
    return _graph


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
    try:
        draft = capture_thought(_get_drafts(), content, tags)
        return _draft_response(draft)
    except Exception as e:
        return {"error": f"Failed to capture thought: {e}"}


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
    try:
        draft = add_task(_get_drafts(), title, description, due_date, priority, tags)
        return _draft_response(draft)
    except Exception as e:
        return {"error": f"Failed to create task: {e}"}


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
    try:
        draft = save_link(_get_drafts(), url, title, description, tags)
        return _draft_response(draft)
    except Exception as e:
        return {"error": f"Failed to save link: {e}"}


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
    try:
        draft = create_note_cmd(_get_drafts(), note_type, title, content, tags)
        return _draft_response(draft)
    except Exception as e:
        return {"error": f"Failed to create note: {e}"}


# ---------------------------------------------------------------------------
# Draft lifecycle tools
# ---------------------------------------------------------------------------


@mcp.tool()
def approve_draft(draft_id: str) -> dict:
    """Approve a draft and write it to the vault.

    Only call this after showing the preview to the user and receiving
    explicit approval. Returns the created note's ID and path.
    """
    try:
        note = _get_drafts().approve_draft(draft_id, _get_vault())
    except KeyError:
        return {"error": f"Draft not found: {draft_id}"}
    except Exception as e:
        return {"error": f"Failed to approve draft: {e}"}
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
    try:
        draft = _get_drafts().update_draft(draft_id, edits)
    except KeyError:
        return {"error": f"Draft not found: {draft_id}"}
    except Exception as e:
        return {"error": f"Failed to update draft: {e}"}
    return _draft_response(draft)


@mcp.tool()
def reject_draft(draft_id: str) -> dict:
    """Discard a draft. The note will not be saved to the vault."""
    try:
        _get_drafts().reject_draft(draft_id)
    except KeyError:
        return {"error": f"Draft not found: {draft_id}"}
    except Exception as e:
        return {"error": f"Failed to reject draft: {e}"}
    return {"status": "rejected", "draft_id": draft_id}


# ---------------------------------------------------------------------------
# Search tools
# ---------------------------------------------------------------------------


@mcp.tool()
def search_vault(
    query: str,
    limit: int = 10,
    note_type: str | None = None,
    include_content: int = 3,
) -> dict:
    """Search the vault using hybrid retrieval (lexical + semantic).

    Returns structured context with ranked results. Optionally filter by note_type.
    """
    try:
        idx = _get_index()
    except RuntimeError:
        return {"error": "Search index not available. Run the rebuild_index tool to build it."}

    try:
        vault = _get_vault()
    except RuntimeError:
        vault = None

    # Wire graph manager into pipeline for graph expansion (if available)
    try:
        graph = _get_graph()
    except RuntimeError:
        graph = None

    config = _config or CortexConfig()
    pipeline = QueryPipeline(
        idx.lexical,
        idx.semantic,
        graph=graph,
        reranker_config=config.reranker,
        vault=vault,
        max_context_tokens=config.mcp.max_context_tokens,
    )

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(pipeline.execute(query, limit))

    results = result.results
    if note_type:
        results = [r for r in results if r.note_type == note_type]

    # Enrich results with dates from vault
    enriched = []
    for i, r in enumerate(results):
        entry = {
            "note_id": r.note_id,
            "title": r.title,
            "score": round(r.score, 4),
            "matched_by": r.matched_by,
            "snippet": r.snippet,
            "note_type": r.note_type,
        }
        if vault:
            try:
                note = vault.get_note(r.note_id)
                entry["created"] = note.created.isoformat()
                entry["modified"] = note.modified.isoformat()
                entry["tags"] = note.tags
                source_url = note.frontmatter.get("source_url")
                if source_url:
                    entry["source_url"] = source_url
                if i < include_content:
                    entry["content"] = note.content
            except (KeyError, FileNotFoundError):
                pass
        enriched.append(entry)

    return {
        "query": result.query,
        "total": len(enriched),
        "explanation": result.explanation,
        "context": result.context,
        "results": enriched,
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
        "frontmatter": note.frontmatter,
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


# ---------------------------------------------------------------------------
# Lifecycle tools
# ---------------------------------------------------------------------------


@mcp.tool()
def edit_note(note_id: str, changes: dict) -> dict:
    """Start an edit on an existing note with a review draft.

    Changes can include: title, content, tags, and arbitrary frontmatter fields.
    Returns a draft with a diff preview — show the preview to the user and ask
    for approval before calling approve_edit.
    """
    try:
        lm = _get_lifecycle()
    except RuntimeError as e:
        return {"error": str(e)}

    try:
        draft = lm.start_edit(note_id, changes)
    except KeyError:
        return {"error": f"Note not found: {note_id}"}

    diff = draft.frontmatter.get("_diff", "")
    return {
        "draft_id": draft.draft_id,
        "preview": draft.render_preview(),
        "diff": diff,
        "note_id": note_id,
    }


@mcp.tool()
def approve_edit(draft_id: str) -> dict:
    """Approve an edit draft and commit changes to the vault.

    Only call this after showing the diff to the user and receiving approval.
    """
    try:
        lm = _get_lifecycle()
    except RuntimeError as e:
        return {"error": str(e)}

    try:
        note = lm.commit_edit(draft_id)
    except (ValueError, KeyError) as e:
        return {"error": str(e)}

    return {
        "note_id": note.id,
        "title": note.title,
        "path": str(note.path),
        "status": "committed",
    }


@mcp.tool()
def archive_note(note_id: str) -> dict:
    """Archive a note — sets status to archived and deprioritizes in search."""
    try:
        lm = _get_lifecycle()
    except RuntimeError as e:
        return {"error": str(e)}

    try:
        note = lm.archive_note(note_id)
    except KeyError:
        return {"error": f"Note not found: {note_id}"}

    return {
        "note_id": note.id,
        "title": note.title,
        "status": "archived",
    }


@mcp.tool()
def unarchive_note(note_id: str) -> dict:
    """Restore an archived note back to active status."""
    try:
        lm = _get_lifecycle()
    except RuntimeError as e:
        return {"error": str(e)}

    try:
        note = lm.unarchive_note(note_id)
    except KeyError:
        return {"error": f"Note not found: {note_id}"}

    return {
        "note_id": note.id,
        "title": note.title,
        "status": "active",
    }


@mcp.tool()
def supersede_note(old_note_id: str, new_note_id: str) -> dict:
    """Mark a note as superseded by a newer note.

    Creates bidirectional links and deprioritizes the old note in search.
    """
    try:
        lm = _get_lifecycle()
    except RuntimeError as e:
        return {"error": str(e)}

    try:
        old_note, new_note = lm.supersede_note(old_note_id, new_note_id)
    except KeyError as e:
        return {"error": f"Note not found: {e}"}

    return {
        "old_note_id": old_note.id,
        "old_status": "superseded",
        "new_note_id": new_note.id,
        "superseded_by": new_note_id,
    }


@mcp.tool()
def detect_stale() -> dict:
    """Detect stale notes that may need review, archival, or categorization.

    Returns notes sorted by staleness score with suggested actions.
    """
    try:
        vault = _get_vault()
        graph = _get_graph()
    except RuntimeError as e:
        return {"error": str(e)}

    config = _config or CortexConfig()
    candidates = detect_stale_notes(vault, graph, config.lifecycle)

    return {
        "total_stale": len(candidates),
        "candidates": [
            {
                "note_id": c.note.id,
                "title": c.note.title,
                "note_type": c.note.note_type,
                "staleness_score": round(c.staleness_score, 2),
                "reasons": c.reasons,
                "suggested_action": c.suggested_action,
            }
            for c in candidates
        ],
    }


# ---------------------------------------------------------------------------
# Workflow tools
# ---------------------------------------------------------------------------


@mcp.tool()
def mcp_process_inbox() -> dict:
    """Process inbox items — list notes in 00-inbox/ with categorization suggestions.

    Returns each inbox item with: summary, suggested target folder, suggested tags,
    and age in days. Present these to the user for triage decisions.
    """
    try:
        vault = _get_vault()
    except RuntimeError as e:
        return {"error": str(e)}

    items = _process_inbox(vault)

    return {
        "total": len(items),
        "items": [
            {
                "note_id": item.note_id,
                "title": item.title,
                "summary": item.summary,
                "suggested_type": item.suggested_type,
                "suggested_folder": item.suggested_folder,
                "suggested_tags": item.suggested_tags,
                "age_days": item.age_days,
                "path": item.path,
            }
            for item in items
        ],
    }


@mcp.tool()
def mcp_generate_review(
    period: str = "weekly",
    target_date: str | None = None,
) -> dict:
    """Generate a weekly or monthly review summary of vault activity.

    Aggregates note counts by type, new captures, completed tasks, active
    projects, and key themes. Present the results to the user as a structured
    review.
    """
    from datetime import date as date_cls

    try:
        vault = _get_vault()
    except RuntimeError as e:
        return {"error": str(e)}

    td = None
    if target_date:
        td = date_cls.fromisoformat(target_date)

    review = _generate_review(vault, period=period, target_date=td)

    return {
        "period": review.period,
        "start_date": review.start_date.isoformat(),
        "end_date": review.end_date.isoformat(),
        "total_notes": review.total_notes,
        "counts_by_type": review.counts_by_type,
        "new_captures": review.new_captures,
        "completed_tasks": review.completed_tasks,
        "active_projects": review.active_projects,
        "key_themes": review.key_themes,
    }


@mcp.tool()
def mcp_summarize_source(note_id: str) -> dict:
    """Summarize a source note — extract key sections, metadata, and structure.

    Returns structured information (headings, URLs, word count, excerpt) for
    Claude to produce a human-readable summary. Works best with source notes
    but accepts any note type.
    """
    try:
        vault = _get_vault()
    except RuntimeError as e:
        return {"error": str(e)}

    try:
        note = vault.get_note(note_id)
    except KeyError:
        return {"error": f"Note not found: {note_id}"}

    return _summarize_source(note)


@mcp.tool()
def mcp_staleness_review() -> dict:
    """Run a staleness review — detect stale notes and suggest triage actions.

    Returns notes sorted by staleness score with reasons and suggested actions
    (archive, categorize, or review). Present results to the user for triage.
    """
    try:
        vault = _get_vault()
        graph = _get_graph()
    except RuntimeError as e:
        return {"error": str(e)}

    config = _config or CortexConfig()
    candidates = _staleness_review(vault, graph, config.lifecycle)

    return {
        "total_stale": len(candidates),
        "candidates": [
            {
                "note_id": c.note.id,
                "title": c.note.title,
                "note_type": c.note.note_type,
                "staleness_score": round(c.staleness_score, 2),
                "reasons": c.reasons,
                "suggested_action": c.suggested_action,
                "path": str(c.note.path),
            }
            for c in candidates
        ],
    }


# ---------------------------------------------------------------------------
# Health check tool
# ---------------------------------------------------------------------------


@mcp.tool()
def mcp_health_check() -> dict:
    """Run a health check on all Cortex subsystems.

    Returns status of: Python process, DuckDB accessibility, vault path
    readability, and embedding model loaded state.
    """
    config = _config or CortexConfig()
    return _health_check(config)
