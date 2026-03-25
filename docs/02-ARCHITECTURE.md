# Technical Design Document: Cortex — Local-First AI-Native Second Brain

**Version:** 0.3
**Date:** 2026-03-14
**Status:** Draft (updated per critical evaluation decisions)
**Companion:** PRD-second-brain.md

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Claude Code                        │
│              (User Interface Layer)                   │
└──────────────────────┬──────────────────────────────┘
                       │ MCP Protocol
                       ▼
┌─────────────────────────────────────────────────────┐
│         MCP Server (FastMCP/streamable-http)            │
│                                                       │
│  ┌─────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │ Capture  │  │  Query   │  │    Workflow        │   │
│  │ Service  │  │  Engine  │  │    Engine          │   │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘   │
│       │              │                 │              │
│       ▼              ▼                 ▼              │
│  ┌─────────────────────────────────────────────────┐ │
│  │              Core Services Layer                 │ │
│  │                                                   │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │ │
│  │  │ Vault    │ │ Index    │ │ Graph            │ │ │
│  │  │ Manager  │ │ Manager  │ │ Manager          │ │ │
│  │  └────┬─────┘ └────┬─────┘ └────────┬─────────┘ │ │
│  └───────┼─────────────┼────────────────┼───────────┘ │
│          │             │                │              │
└──────────┼─────────────┼────────────────┼─────────────┘
           ▼             ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Obsidian   │ │   DuckDB     │ │  Graph DB    │
│   Vault      │ │   + LanceDB  │ │  (NetworkX)   │
│   (markdown) │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Key Architectural Decisions

1. **FastMCP 3.x with streamable-http transport as the service backbone.** Decorator-based tool registration with automatic schema generation from type hints. Runs as a single background HTTP server (`cortex serve`) on `127.0.0.1:8757`, allowing multiple clients (Claude Code, Claude Desktop) to connect simultaneously. Managed via `cortex install` (LaunchAgent) and `cortex restart`. Falls back to stdio mode (`cortex stdio`) for single-client use.

2. **Three storage backends, one source of truth.** The Obsidian vault is canonical. DuckDB holds the full-text index and structured metadata. LanceDB holds vector embeddings. NetworkX (persisted via GraphML) holds the knowledge graph. All derived stores are rebuildable from the vault.

3. **Local-only embeddings.** Sentence-transformers running in-process. No API calls for core functionality.

---

## 2. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Language | Python 3.14+ | Rich ML/NLP ecosystem, fast prototyping |
| MCP Server | FastMCP 3.x | Decorator-based tool registration, auto schema from type hints, streamable-http transport for multi-client access |
| Project Management | uv | Fast, reliable Python package management |
| Full-text Search | DuckDB FTS | Embedded, no external service, SQL-friendly |
| Vector Store | LanceDB | Embedded, local-first, columnar, fast |
| Embeddings | sentence-transformers (`nomic-embed-text`) | 768-dim vectors, runs on CPU, good quality |
| Graph Store | NetworkX + GraphML | In-memory graph with disk persistence via GraphML serialization |
| Markdown Parsing | python-frontmatter + mistune | Frontmatter extraction + markdown AST |
| File Watching | watchdog | Cross-platform file system events |
| Reranking | Heuristic (recency, type, links, status) | Local scoring without model calls; cross-encoder deferred to future |
| MCP SDK | FastMCP (Python SDK) | Official MCP protocol implementation |
| Task Runner | just (justfile) or Makefile | Dev commands, index rebuilds |
| Testing | pytest + pytest-asyncio | Async-aware testing |
| Config | Pydantic Settings | Typed config with env var support |
| Containerization | Docker + Docker Compose | One-command setup, reproducible environment, no local Python install needed |

### Why These Choices

**DuckDB over SQLite FTS5:** DuckDB's full-text search is more capable (BM25 scoring, better tokenization) and it doubles as the structured metadata store. Single embedded database for all relational needs.

**LanceDB over ChromaDB/FAISS:** LanceDB is truly embedded (no server process), stores data in Lance columnar format on disk, supports filtering, and handles incremental updates well. No separate vector DB process needed.

**NetworkX with GraphML persistence:** NetworkX is the most mature Python graph library — battle-tested, well-documented, and has a rich set of graph algorithms (shortest paths, connected components, centrality, community detection). The trade-off is that it's in-memory only, so we persist the graph to disk via GraphML serialization. On load, the graph is deserialized into memory. GraphML is human-readable XML, making it easier to inspect and version control. For a vault of 1,000–5,000 notes this is fast (sub-second load times) and keeps the dependency footprint minimal. If the vault grows beyond ~10K nodes+edges and load times become noticeable, we can evaluate migrating to an embedded graph DB in the future.

**sentence-transformers `nomic-embed-text`:** Fewer moving parts. No separate Ollama process needed. `nomic-embed-text` is trained on diverse data, produces 768-dim vectors with high quality semantic representations, runs on CPU in ~100ms per embedding, and is optimized for retrieval tasks.

---

## 3. Project Structure

```
cortex/
├── pyproject.toml                 # Project config, dependencies
├── Dockerfile                     # Multi-stage build (deps → model → runtime)
├── docker-compose.yml             # One-command orchestration with volume mounts
├── .dockerignore                  # Exclude vault data, caches, local configs
├── justfile                       # Dev commands (including Docker targets)
├── settings.yaml                  # User configuration
├── README.md
│
├── src/
│   └── cortex/
│       ├── __init__.py
│       ├── config.py              # Pydantic settings
│       ├── main.py                # FastMCP server entry
│       │
│       ├── vault/                 # Vault management
│       │   ├── __init__.py
│       │   ├── manager.py         # Read/write notes, manage folders
│       │   ├── parser.py          # Frontmatter + markdown parsing
│       │   ├── templates.py       # Note template generation
│       │   └── watcher.py         # File system watcher
│       │
│       ├── index/                 # Search indexes
│       │   ├── __init__.py
│       │   ├── manager.py         # Index lifecycle (build, update, rebuild)
│       │   ├── lexical.py         # DuckDB full-text search
│       │   ├── semantic.py        # LanceDB vector search
│       │   └── models.py          # Embedding model management
│       │
│       ├── graph/                 # Knowledge graph
│       │   ├── __init__.py
│       │   ├── manager.py         # Graph lifecycle
│       │   ├── builder.py         # Vault → graph construction
│       │   └── queries.py         # Graph query patterns
│       │
│       ├── query/                 # Query pipeline
│       │   ├── __init__.py
│       │   ├── pipeline.py        # Orchestrate retrieval stages
│       │   ├── fusion.py          # Result merging (RRF)
│       │   ├── reranker.py        # Heuristic reranking
│       │   └── context.py         # Context assembly for Claude
│       │
│       ├── capture/               # Capture commands
│       │   ├── __init__.py
│       │   ├── draft.py           # Draft generation & review-before-create flow
│       │   ├── thought.py
│       │   ├── task.py
│       │   ├── link.py
│       │   └── note.py
│       │
│       ├── lifecycle/             # Note lifecycle management
│       │   ├── __init__.py
│       │   ├── manager.py         # LifecycleManager (edit, archive, supersede)
│       │   └── staleness.py       # Staleness detection heuristics
│       │
│       ├── workflow/              # Automated workflows
│       │   ├── __init__.py
│       │   ├── inbox.py           # Inbox processing
│       │   ├── review.py          # Weekly/monthly reviews
│       │   ├── summarize.py       # Source summarization
│       │   └── cluster.py         # Concept clustering
│       │
│       └── mcp/                   # MCP server layer
│           ├── __init__.py
│           ├── server.py          # MCP tool definitions
│           └── tools.py           # Tool implementations
│
├── tests/
│   ├── conftest.py                # Fixtures (temp vault, test indexes)
│   ├── test_vault/
│   ├── test_index/
│   ├── test_graph/
│   ├── test_query/
│   ├── test_capture/
│   ├── test_lifecycle/            # Edit, archive, supersede, staleness tests
│   └── test_workflow/
│
├── evals/                         # Retrieval eval framework
│   ├── golden_dataset.json        # Annotated query → expected-results pairs
│   ├── harness.py                 # Eval runner: execute queries, compute metrics
│   ├── metrics.py                 # MRR, Precision@K, NDCG, lifecycle-specific metrics
│   ├── snapshots/                 # Versioned score snapshots for regression tracking
│   └── README.md                  # How to run evals, interpret results, add cases
│
├── vault/                         # Default vault location
│   ├── 00-inbox/
│   ├── 01-daily/
│   ├── 02-tasks/
│   ├── 10-sources/
│   ├── 20-concepts/
│   ├── 30-permanent/
│   ├── 40-projects/
│   ├── 50-reviews/
│   └── _templates/
│
├── scripts/
│   └── docker-entrypoint.sh       # First-run init (vault scaffold, model warm-up)
│
└── data/                          # Derived data (rebuildable)
    ├── cortex.duckdb              # Full-text index + metadata
    ├── embeddings/                # LanceDB tables
    ├── graph/                     # NetworkX GraphML files
    └── drafts/                    # File-persisted draft notes
```

---

## 4. Component Design

### 4.1 Vault Manager

**Responsibility:** CRUD operations on the Obsidian vault. The only component that writes markdown files.

```python
class VaultManager:
    def __init__(self, vault_path: Path, config: CortexConfig): ...

    # Read operations
    def get_note(self, note_id: str) -> Note: ...
    def list_notes(self, folder: str = None, note_type: str = None) -> list[Note]: ...
    def get_daily_note(self, date: date = None) -> Note: ...

    # Write operations
    def create_note(self, note_type: str, title: str, content: str, metadata: dict) -> Note: ...
    def update_note(self, note_id: str, content: str = None, metadata: dict = None) -> Note: ...
    def move_note(self, note_id: str, target_folder: str) -> Note: ...

    # Parsing
    def parse_note(self, path: Path) -> Note: ...
    def extract_links(self, note: Note) -> list[Link]: ...
    def extract_tags(self, note: Note) -> list[str]: ...
```

**Data model:**

```python
@dataclass
class Note:
    id: str              # UUID
    title: str
    note_type: str       # inbox, daily, task, source, concept, permanent, project, review
    path: Path           # Relative to vault root
    content: str         # Raw markdown body (without frontmatter)
    frontmatter: dict    # Parsed YAML frontmatter
    created: datetime
    modified: datetime
    tags: list[str]
    links: list[str]     # Outgoing wikilinks (note IDs or titles)
    status: str          # draft, active, archived, superseded
    # Lifecycle fields
    supersedes: str = None       # Note ID this replaces
    superseded_by: str = None    # Note ID that replaced this
    archived_date: datetime = None

@dataclass
class Link:
    source_id: str
    target_id: str       # Resolved note ID, or null if unresolved
    target_title: str    # Raw link text
    link_type: str       # wikilink, markdown_link, frontmatter_related
```

### 4.2 Draft & Review-Before-Create Flow

**Responsibility:** Generate note drafts in memory and manage the approve/edit/reject lifecycle. No note is ever written to the vault without explicit user approval.

**Design rationale:** The draft system is a separate layer that sits between the capture commands and the VaultManager. Capture commands produce a `NoteDraft`; the MCP server presents it to the user via Claude; only after approval does it call `VaultManager.create_note()`.

```python
@dataclass
class NoteDraft:
    """An in-memory note that has not been saved to the vault yet."""
    draft_id: str            # Temporary ID (UUID) for tracking this draft
    note_type: str           # inbox, task, source, concept, permanent, project
    title: str
    content: str             # Markdown body
    frontmatter: dict        # Complete frontmatter (tags, status, etc.)
    target_folder: str       # Where it will be saved (e.g., "00-inbox/")
    target_filename: str     # Proposed filename

    def render_preview(self) -> str:
        """Render the draft as a formatted preview string for Claude to show the user."""
        ...

    def render_markdown(self) -> str:
        """Render the full markdown file (frontmatter + body) for writing to disk."""
        ...

    def apply_edits(self, edits: dict) -> "NoteDraft":
        """
        Return a new NoteDraft with user-requested changes applied.
        edits can include: {title, content, tags, folder, frontmatter overrides}
        """
        ...


class DraftManager:
    """Manages the lifecycle of note drafts with file-based persistence."""

    def __init__(self, drafts_dir: Path):
        self._drafts_dir = drafts_dir
        self._drafts_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_drafts()  # Delete drafts >24h old on startup

    def _cleanup_stale_drafts(self) -> None:
        """Remove draft files older than 24 hours (not approved)."""
        ...

    def create_draft(self, note_type: str, title: str, content: str,
                     metadata: dict = None) -> NoteDraft:
        """Generate a draft using templates. Persist to data/drafts/{draft_id}.json."""
        ...

    def get_draft(self, draft_id: str) -> NoteDraft:
        """Retrieve a pending draft from file for preview or editing."""
        ...

    def update_draft(self, draft_id: str, edits: dict) -> NoteDraft:
        """Apply user edits, save updated draft to file, and return the updated draft."""
        ...

    def approve_draft(self, draft_id: str, vault: VaultManager,
                      index: IndexManager, graph: GraphManager) -> Note:
        """
        Approve a draft: write to vault, index it, add to graph.
        Returns the finalized Note. Deletes draft file after approval.
        """
        ...

    def reject_draft(self, draft_id: str) -> None:
        """Discard a draft. Deletes the draft file."""
        ...
```

**MCP interaction pattern:**

The review-before-create flow is implemented as a two-step (or multi-step) MCP tool interaction:

1. **Step 1 — `capture_*` or `create_note` tool call:** Claude calls a capture tool (e.g., `capture_thought`). The tool generates a `NoteDraft`, persists it to `data/drafts/{draft_id}.json`, and returns the preview to Claude along with the `draft_id`.

2. **Step 2 — Claude presents the preview:** Claude shows the user the rendered preview and asks: approve, edit, or reject.

3. **Step 3a — `approve_draft` tool call:** If the user approves, Claude calls `approve_draft(draft_id)`. The note is written to the vault and indexed. The draft file is deleted.

3. **Step 3b — `update_draft` + loop:** If the user wants edits, Claude calls `update_draft(draft_id, edits)`, the draft file is updated, and it gets a new preview. This can repeat.

3. **Step 3c — `reject_draft` tool call:** If the user rejects, Claude calls `reject_draft(draft_id)`. The draft file is deleted.

```
User: "Capture this thought: distributed caching might solve our latency issue"

Claude → MCP: capture_thought(content="distributed caching might solve our latency issue")
MCP → Claude: {draft_id: "abc123", preview: "## Inbox Note\nTitle: Distributed caching...\nTags: #idea\n..."}

Claude → User: "Here's the draft note I've prepared:
                [shows preview]
                Would you like to save it as-is, make changes, or discard it?"

User: "Change the tags to #architecture #performance"

Claude → MCP: update_draft(draft_id="abc123", edits={tags: ["architecture", "performance"]})
MCP → Claude: {draft_id: "abc123", preview: "## Inbox Note\nTitle: ...\nTags: #architecture #performance\n..."}

Claude → User: "Updated — here's the revised draft:
                [shows preview]
                Save this?"

User: "Yes"

Claude → MCP: approve_draft(draft_id="abc123")
MCP → Claude: {note_id: "def456", path: "00-inbox/2026-03-14-thought-{hash}-distributed-caching.md"}

Claude → User: "Saved and indexed."
```

**Draft cleanup:** Drafts are persisted as JSON files in `data/drafts/{draft_id}.json`. On startup, the DraftManager automatically deletes any draft files older than 24 hours. This prevents stale drafts from accumulating.

---

### 4.3 Note Lifecycle Manager

**Responsibility:** Manage the full lifecycle of notes after creation — editing, archival, supersession, and staleness detection. Ensures all three indexes stay consistent after every mutation.

```python
class LifecycleManager:
    """Coordinates note mutations across vault, indexes, and graph."""

    def __init__(self, vault: VaultManager, index: IndexManager,
                 graph: GraphManager, draft_mgr: DraftManager):
        self._vault = vault
        self._index = index
        self._graph = graph
        self._draft_mgr = draft_mgr

    # --- Edit flow ---
    def start_edit(self, note_id: str, changes: dict) -> NoteDraft:
        """
        Load existing note, apply changes, return a NoteDraft for review.
        The draft includes a `diff` field showing what changed.
        changes: {content: str, title: str, tags: list, ...}
        Does NOT write to disk.
        """
        ...

    def commit_edit(self, draft_id: str) -> Note:
        """
        Approve an edit draft. Overwrites the file,
        updates modified timestamp, and re-indexes across all stores.
        """
        note = self._draft_mgr.approve_draft(draft_id, ...)
        # Critical: re-index atomically
        self._index.reindex_note(note)   # DuckDB + LanceDB
        self._graph.update_note(note)     # NetworkX
        return note

    # --- Archival flow ---
    def archive_note(self, note_id: str) -> Note:
        """
        Set status='archived', set archived_date, re-index.
        Archived notes get a scoring penalty in query pipeline.
        """
        ...

    def unarchive_note(self, note_id: str) -> Note:
        """Restore an archived note to active status."""
        ...

    # --- Supersession flow ---
    def supersede_note(self, old_note_id: str, new_note_id: str) -> tuple[Note, Note]:
        """
        Mark old note as superseded, link both notes bidirectionally,
        add SUPERSEDES edge to graph, re-index both notes.
        Returns (old_note, new_note) after update.
        """
        old = self._vault.get_note(old_note_id)
        new = self._vault.get_note(new_note_id)

        # Update frontmatter on both
        self._vault.update_note(old_note_id, metadata={
            "status": "superseded",
            "superseded_by": new_note_id
        })
        self._vault.update_note(new_note_id, metadata={
            "supersedes": old_note_id
        })

        # Graph edge
        self._graph.add_edge(new_note_id, old_note_id, rel_type="SUPERSEDES")

        # Re-index both
        self._index.reindex_note(old)
        self._index.reindex_note(new)
        return (old, new)

    # --- Staleness detection ---
    def detect_stale_notes(self) -> list[StaleCandidate]:
        """
        Identify notes that may be outdated using per-type thresholds:
        - inbox/task: 30 days without modification
        - source: 90 days without modification
        - concept/permanent: 365 days without modification
        - evergreen: never marked stale (marked with evergreen: true tag)

        A note is stale if ALL of:
        - status is 'active'
        - modified date > type-specific threshold ago
        - no inbound LINKS_TO edges in the graph (orphan)

        Returns candidates sorted by staleness score (most stale first).
        """
        ...

@dataclass
class StaleCandidate:
    note: Note
    staleness_score: float     # 0.0 = fresh, 1.0 = very stale
    reasons: list[str]         # ["no inbound links", "not modified in 120 days", ...]
    suggested_action: str      # "archive", "review", "merge with <note>"
```

**Index consistency guarantee:**

Every mutation (edit, archive, supersede) must update all three stores or none. The `LifecycleManager` follows this sequence:

1. Write changes to the vault file (source of truth).
2. Update DuckDB (metadata + FTS re-index).
3. Update LanceDB (re-embed the changed content, replace old vectors).
4. Update NetworkX (modify node attributes, add/remove edges, save GraphML).

If any step fails after the vault write, the system logs the inconsistency and queues a repair task. The `rebuild_index` admin tool can always fully reconstruct all derived stores from the vault.

**Scoring penalty for archived/superseded notes:**

The query pipeline applies status-based score multipliers during fusion:

```python
STATUS_SCORE_MULTIPLIERS = {
    "active": 1.0,
    "draft": 0.8,
    "archived": 0.3,       # Heavily penalized but still findable
    "superseded": 0.2,     # Almost always ranks below its replacement
}
```

These multipliers are applied after RRF fusion but before heuristic reranking.

**Context annotation for superseded notes:**

When a superseded note appears in results, the `ContextAssembler` appends:

```
⚠ This note was superseded by: [newer note title] (id: xxx) on [date].
```

This ensures Claude never presents outdated information without flagging it.

---

### 4.4 Lexical Index (DuckDB)

**Responsibility:** Full-text search with BM25 scoring. Also stores structured metadata for SQL queries.

```sql
-- Core notes table with FTS
CREATE TABLE notes (
    id VARCHAR PRIMARY KEY,
    title VARCHAR,
    note_type VARCHAR,
    path VARCHAR,
    content TEXT,
    tags VARCHAR[],              -- array for SQL filtering
    tags_text VARCHAR,           -- space-separated for FTS indexing
    status VARCHAR,              -- draft, active, archived, superseded
    source_url VARCHAR,
    created TIMESTAMP,
    modified TIMESTAMP,
    -- Lifecycle fields
    supersedes VARCHAR,          -- note ID this replaces
    superseded_by VARCHAR,       -- note ID that replaced this
    archived_date TIMESTAMP
);

-- DuckDB FTS index
PRAGMA create_fts_index('notes', 'id', 'title', 'content', 'tags_text');
```

```python
class LexicalIndex:
    def __init__(self, db_path: Path): ...

    def index_note(self, note: Note) -> None: ...
    def remove_note(self, note_id: str) -> None: ...
    def rebuild(self, notes: list[Note]) -> None: ...

    def search(self, query: str, limit: int = 20, filters: dict = None) -> list[SearchResult]: ...
    # filters: {note_type: str, tags: list, date_range: tuple, status: str}
```

### 4.3 Semantic Index (LanceDB)

**Responsibility:** Vector similarity search using local embeddings.

```python
class SemanticIndex:
    def __init__(self, db_path: Path, model_name: str = "nomic-embed-text"): ...

    def embed(self, text: str) -> np.ndarray: ...
    def index_note(self, note: Note) -> None: ...
    def remove_note(self, note_id: str) -> None: ...
    def rebuild(self, notes: list[Note]) -> None: ...

    def search(self, query: str, limit: int = 20, filters: dict = None) -> list[SearchResult]: ...
```

**Chunking strategy:**

- Semantic-boundary splitting: split notes on paragraph boundaries first, then on sentence boundaries if a paragraph exceeds size limits.
- Target chunk size: ~300 tokens; maximum chunk size: 500 tokens.
- Use `nomic-embed-text` tokenizer for accurate token counting.
- Drop note-level embedding; rely on paragraph/sentence chunks for retrieval.
- Note-score boosting: if multiple chunks from the same note rank highly in fusion results, boost the final score for that note.

**LanceDB schema:**

```python
# LanceDB table schema
{
    "id": str,              # chunk ID (note_id or note_id__chunk_N)
    "note_id": str,         # parent note ID
    "title": str,
    "note_type": str,
    "text": str,            # chunk text
    "vector": list[float],  # 768-dim embedding
    "tags": list[str],
    "created": str,
}
```

### 4.4 Knowledge Graph (NetworkX)

**Responsibility:** Relationship-aware queries — neighbors, paths, clusters.

**Graph model for Phase 1:** A simplified `networkx.MultiDiGraph` (directed, allows multiple edges between nodes) with note nodes and project nodes only.

```python
import networkx as nx

# Phase 1 — Simplified node types:
#   "note"    → {id, title, note_type, path}
#   "project" → {id, name}
#
# Phase 1 — Edge types only:
#   LINKS_TO → note-to-note wikilinks
#   BELONGS_TO_PROJECT → note belongs to a project
#
# Future phases will add:
#   concept, topic, person nodes and their associated edges

# Example graph construction:
G = nx.MultiDiGraph()
G.add_node("note-abc", node_type="note", title="Vector DB overview", note_type="concept")
G.add_node("project-cortex", node_type="project", name="Cortex")
G.add_edge("note-abc", "project-cortex", rel_type="BELONGS_TO_PROJECT")
```

```python
class GraphManager:
    def __init__(self, graph_path: Path):
        """Load graph from GraphML file, or create empty graph."""
        self._graph_path = graph_path
        self._graph: nx.MultiDiGraph = self._load_or_create()

    def _load_or_create(self) -> nx.MultiDiGraph: ...
    def save(self) -> None:
        """Persist graph to disk via GraphML serialization."""
        ...

    def build_from_vault(self, notes: list[Note]) -> None: ...
    def update_note(self, note: Note) -> None: ...
    def remove_note(self, note_id: str) -> None: ...

    # Query patterns
    def get_neighbors(self, note_id: str, depth: int = 1) -> list[GraphNode]:
        """BFS to given depth using nx.bfs_edges.""" ...
    def find_path(self, source_id: str, target_id: str) -> list[GraphNode]:
        """Shortest path using nx.shortest_path.""" ...
    def get_cluster(self, note_id: str, max_nodes: int = 20) -> list[GraphNode]:
        """Connected component or ego graph using nx.ego_graph.""" ...
    def get_project_notes(self, project_id: str) -> list[GraphNode]:
        """All nodes with BELONGS_TO_PROJECT edge to project_id.""" ...
```

**Persistence strategy:** The graph is serialized to `data/graph/graph.graphml` via `nx.write_graphml()`. On startup, the `GraphManager` loads the file with `nx.read_graphml()`. After any mutation (add/update/remove), the graph is saved. For safety, a backup (`graph.graphml.bak`) is kept before each write. GraphML is human-readable XML, making it easier to inspect and version-control. The graph can always be fully rebuilt from the vault if the GraphML file is corrupted or lost.

### 4.5 Query Pipeline

**Responsibility:** Orchestrate multi-stage retrieval with parallel execution of all retrieval systems.

```
Query → [Lexical, Semantic, Graph] (parallel) → Fusion → Heuristic Reranking → Context Assembly
```

**Every query runs all three retrieval systems in parallel:**

- **Lexical:** Full-text search via DuckDB BM25 (exact and fuzzy term matching)
- **Semantic:** Vector similarity search via LanceDB (semantic relatedness)
- **Graph:** Relationship queries via NetworkX (LINKS_TO, BELONGS_TO_PROJECT edges)

No routing/classification step — simpler architecture with no query type ambiguity.

```python
class QueryPipeline:
    def __init__(self, lexical: LexicalIndex, semantic: SemanticIndex,
                 graph: GraphManager): ...

    async def execute(self, query: str, limit: int = 10) -> QueryResult: ...

class QueryResult:
    query: str
    results: list[RankedResult]
    context: str              # Assembled context string for Claude
    explanation: str          # Human-readable explanation of retrieval (which systems contributed)
```

**Fusion strategy — Reciprocal Rank Fusion (RRF):**

```python
def reciprocal_rank_fusion(result_lists: list[list[SearchResult]], k: int = 60) -> list[SearchResult]:
    """
    Merge ranked lists from all three systems using RRF.
    score(d) = sum(1 / (k + rank_i(d))) for each list i
    """
```

### 4.6 Context Assembler

**Responsibility:** Format retrieval results into structured context that Claude can use to synthesize an answer.

```python
class ContextAssembler:
    def assemble(self, results: list[RankedResult], query: str, max_tokens: int = 4000) -> str:
        """
        Returns a structured context block:

        ## Query: {query}
        ## Retrieved {n} results via {retrieval_methods}

        ### Result 1: {title} (score: {score}, via: {source})
        {relevant_excerpt}
        Tags: {tags} | Links: {links} | Created: {date}

        ### Result 2: ...
        """
```

### 4.7 MCP Server

**Responsibility:** Expose Cortex capabilities as MCP tools that Claude Code can call natively.

```python
# MCP Tool definitions
tools = [
    # Capture tools (all return a draft preview — never write directly to vault)
    Tool("capture_thought", "Generate a draft inbox note from a thought", {...}),
    Tool("add_task", "Generate a draft task note with optional due date", {...}),
    Tool("save_link", "Generate a draft source note from a URL", {...}),
    Tool("create_note", "Generate a draft note (source, concept, project)", {...}),

    # Draft lifecycle tools
    Tool("approve_draft", "Approve a draft and save it to the vault", {draft_id: str}),
    Tool("update_draft", "Apply edits to a pending draft", {draft_id: str, edits: dict}),
    Tool("reject_draft", "Discard a draft without saving", {draft_id: str}),

    # Note lifecycle tools
    Tool("edit_note", "Start editing an existing note. Returns a draft with diff for review", {note_id: str, changes: dict}),
    Tool("archive_note", "Archive a note (reduces its ranking in search results)", {note_id: str}),
    Tool("unarchive_note", "Restore an archived note to active status", {note_id: str}),
    Tool("supersede_note", "Mark a note as superseded by a newer note", {old_note_id: str, new_note_id: str}),
    Tool("detect_stale", "Find notes that may be outdated and need review", {days_threshold: int}),

    # Query tools
    Tool("search_vault", "Search the knowledge base with natural language", {
        query: str, limit: int = 10, note_type: str | None = None,
        created_after: str | None = None, created_before: str | None = None,
        include_content: int = 3,
    }),
    Tool("explore_connections", "Find connections between notes or concepts", {...}),
    Tool("get_note", "Retrieve a specific note by ID or title", {...}),

    # Workflow tools
    Tool("process_inbox", "Process and categorize inbox items", {...}),
    Tool("generate_review", "Generate a weekly or monthly review", {...}),
    Tool("summarize_source", "Generate a summary of a source note", {...}),
    Tool("staleness_review", "Run staleness detection and present candidates for triage", {...}),

    # Admin tools
    Tool("rebuild_index", "Rebuild all search indexes from vault", {...}),
    Tool("vault_stats", "Get vault statistics", {...}),
    Tool("run_eval", "Run retrieval eval suite and return scores", {suite: str}),
]
```

**Important:** Capture tools must include clear `description` fields in their MCP tool definitions that instruct Claude to always show the returned preview to the user and ask for approval before calling `approve_draft`. This is the enforcement mechanism — the MCP tool description acts as a behavioral contract with Claude.

---

## 5. Data Flow Diagrams

### 5.1 Capture Flow (with Review-Before-Create)

```
User says "Capture this thought: X"
    → Claude calls MCP tool: capture_thought(content="X")
        → DraftManager.create_draft(type="inbox", content="X")
            → generates NoteDraft using template, persists to data/drafts/{draft_id}.json
        → returns {draft_id, preview, target_folder, target_filename}
    → Claude shows the user the preview and asks: approve, edit, or reject?

    [If user approves]
    → Claude calls MCP tool: approve_draft(draft_id="abc123")
        → DraftManager.approve_draft(draft_id)
            → VaultManager.create_note(from draft)
                → writes 00-inbox/2026-03-14-thought-{hash}-distributed-caching.md
            → IndexManager.index_note(note)
                → LexicalIndex.index_note(note)
                → SemanticIndex.index_note(note)
            → GraphManager.update_note(note)
        → returns {note_id, title, path}
    → Claude confirms: "Saved and indexed."

    [If user requests edits]
    → Claude calls MCP tool: update_draft(draft_id="abc123", edits={tags: [...]})
        → DraftManager.update_draft(draft_id, edits)
        → returns {draft_id, preview}  (updated)
    → Claude shows revised preview, asks again
    → (loop until approve or reject)

    [If user rejects]
    → Claude calls MCP tool: reject_draft(draft_id="abc123")
        → DraftManager.reject_draft(draft_id)
    → Claude confirms: "Draft discarded."
```

### 5.2 Edit Flow (with Review)

```
User says "Update my note about caching — we switched from Redis to Memcached"
    → Claude calls MCP tool: search_vault(query="caching Redis")
        → returns top results
    → Claude shows candidates, user confirms which note (e.g., note_id="xyz789")

    → Claude calls MCP tool: edit_note(note_id="xyz789", changes={content: "...Memcached..."})
        → LifecycleManager.start_edit(note_id, changes)
            → loads current note from vault
            → generates updated NoteDraft with diff
            → stores draft in DraftManager
        → returns {draft_id, preview, diff}
    → Claude shows the user the diff and updated preview

    [If user approves]
    → Claude calls MCP tool: approve_draft(draft_id="edit-xyz")
        → LifecycleManager.commit_edit(draft_id)
            → VaultManager.update_note(note_id, new_content)
                → overwrites file, updates modified timestamp
            → IndexManager.reindex_note(note)
                → DuckDB: UPDATE row
                → LanceDB: delete old vectors, insert new vectors
            → GraphManager.update_note(note)
                → update node attrs, recalculate edges from new links
        → returns {note_id, path}
    → Claude confirms: "Note updated and re-indexed."
```

### 5.3 Supersession Flow

```
User says "This new note on caching supersedes my old Redis caching note"
    → Claude calls MCP tool: supersede_note(old_note_id="xyz789", new_note_id="abc456")
        → LifecycleManager.supersede_note(old_id, new_id)
            → old note: status="superseded", superseded_by="abc456"
            → new note: supersedes="xyz789"
            → GraphManager: add SUPERSEDES edge (abc456 → xyz789)
            → re-index both notes in DuckDB + LanceDB
        → returns {old_note, new_note}
    → Claude confirms: "Old note marked as superseded. Future searches will prefer the new version."

Later, user searches "caching strategies":
    → Query pipeline runs normally
    → Both notes match, but old note gets 0.2x score multiplier (superseded)
    → New note ranks higher
    → If old note still appears, ContextAssembler appends:
      "⚠ Superseded by: Memcached Caching Strategy (abc456) on 2026-05-10"
```

### 5.4 Query Flow

```
User says "What do I know about vector databases?"
    → Claude calls MCP tool: search_vault(query="vector databases")
        → QueryPipeline.execute(query)
            → [Lexical, Semantic, Graph] search in PARALLEL:
                → SemanticIndex.search("vector databases", limit=20)
                → LexicalIndex.search("vector databases", limit=20)
                → GraphManager.get_neighbors(top_result_ids)
            → Fusion.merge(lexical_results, semantic_results, graph_results) via RRF
            → Apply STATUS_SCORE_MULTIPLIERS (active=1.0, archived=0.3, superseded=0.2)
            → HeuristicReranker.rerank(fused_results, query) — boost recency, type, links, status
            → ContextAssembler.assemble(reranked_results)
                → annotate any superseded results with warning
        → returns {context, results, explanation}
    → Claude synthesizes an answer using the structured context

User says "What notes did I add last Friday?"
    → Claude calls MCP tool: search_vault(query="*", created_after="2026-03-20", created_before="2026-03-20")
        → date_range filter pushed to LexicalIndex for efficient DuckDB filtering
        → semantic results post-filtered by created date
        → returns only notes created on that day
```

---

## 6. Configuration

```yaml
# settings.yaml
vault:
  path: "./vault"                      # Path to Obsidian vault
  templates_folder: "_templates"

index:
  db_path: "./data/cortex.duckdb"
  embeddings_path: "./data/embeddings"
  graph_path: "./data/graph"

embeddings:
  model: "nomic-embed-text"             # sentence-transformers model
  chunk_size: 300                       # target tokens per chunk
  chunk_max: 500                        # max tokens per chunk

search:
  default_limit: 10
  fusion_k: 60                          # RRF parameter
```

---

## 6a. Docker Design

### Overview

The entire Cortex system is containerized so that users can go from clone to working system with a single `docker compose up`. No local Python installation, no manual dependency management, no model download steps. Docker is the primary deployment mechanism; bare-metal `uv run` remains available for development.

### Dockerfile (Multi-Stage Build)

The Dockerfile uses a multi-stage build to keep the final image lean and make rebuilds fast when only code changes:

```dockerfile
# Stage 1: Dependencies
FROM python:3.14-slim AS deps
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# Stage 2: Model download (cached separately — ~500MB, rarely changes)
FROM deps AS models
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')"

# Stage 3: Runtime
FROM python:3.14-slim AS runtime
WORKDIR /app
COPY --from=models /app/.venv /app/.venv
COPY --from=models /root/.cache/huggingface /root/.cache/huggingface
COPY src/ ./src/
COPY settings.yaml pyproject.toml ./
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uv", "run", "cortex"]
```

**Key design decisions:**

- **Model download in a separate stage.** The `nomic-embed-text` model is ~500MB. Caching it in its own build stage means code-only changes don't re-download the model.
- **No vault or data baked into the image.** The vault and data directories are always volume-mounted. The image is stateless.
- **`--no-dev` dependencies.** Test/dev dependencies excluded from the production image.

### Docker Compose

```yaml
# docker-compose.yml
services:
  cortex:
    build: .
    volumes:
      - ${CORTEX_VAULT_PATH:-./vault}:/app/vault
      - cortex-data:/app/data
    environment:
      - CORTEX_VAULT_PATH=/app/vault
      - CORTEX_DATA_PATH=/app/data
    stdin_open: true     # Required for stdio MCP transport
    tty: false
    # No ports exposed — stdio transport only

volumes:
  cortex-data:           # Named volume for derived data (indexes, graph, drafts)
```

**Volume strategy:**

- **Vault:** Bind-mounted from the host filesystem (`CORTEX_VAULT_PATH` env var, defaults to `./vault`). This is the user's Obsidian vault — it must be accessible from both Obsidian (on host) and Cortex (in container).
- **Data:** Named Docker volume (`cortex-data`) for derived data (DuckDB, LanceDB, GraphML, drafts). This is rebuildable from the vault, so it doesn't need to be backed up. Named volume ensures persistence across container restarts without cluttering the host filesystem.

### Claude Code MCP Configuration

Claude Code needs to spawn the containerized MCP server via stdio. The MCP config in Claude Code's `settings.json`:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "docker",
      "args": [
        "compose", "-f", "/path/to/cortex/docker-compose.yml",
        "run", "--rm", "-i", "cortex"
      ]
    }
  }
}
```

**Alternative (direct `docker run`):**

```json
{
  "mcpServers": {
    "cortex": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/vault:/app/vault",
        "-v", "cortex-data:/app/data",
        "cortex:latest"
      ]
    }
  }
}
```

The `-i` flag keeps stdin open for the stdio MCP transport. `--rm` cleans up the container after Claude Code disconnects.

### Docker Entrypoint Script

`scripts/docker-entrypoint.sh` handles first-run initialization:

```bash
#!/bin/bash
set -e

# First-run: scaffold vault structure if empty
if [ ! -d "/app/vault/00-inbox" ]; then
    echo "First run detected — scaffolding vault structure..." >&2
    uv run cortex-init --vault-path /app/vault
fi

# First-run: build indexes if data dir is empty
if [ ! -f "/app/data/cortex.duckdb" ]; then
    echo "No indexes found — building from vault..." >&2
    uv run cortex-rebuild
fi

# Warm up embedding model (loads into memory)
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')" 2>/dev/null

exec "$@"
```

### Development vs Production

| Aspect | Development (bare metal) | Production (Docker) |
|---|---|---|
| Python | Local install via `uv` | Baked into image |
| Dependencies | `uv sync` | Built into image |
| Embedding model | Downloaded on first run | Baked into image (cached layer) |
| Vault access | Direct filesystem | Bind mount |
| Data persistence | Local `./data` directory | Named Docker volume |
| MCP config | `uv run cortex` command | `docker compose run` command |
| Hot reload | Yes (watchdog + direct file access) | Rebuild image or mount `src/` as volume |
| GPU access | Direct CUDA/MPS | `--gpus` flag or `deploy.resources` in compose |

### GPU Support (Optional)

For users with NVIDIA GPUs who want faster embedding generation:

```yaml
# docker-compose.gpu.yml (override file)
services:
  cortex:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Usage: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up`

The embedding model (`nomic-embed-text`) runs on CPU by default and is fast enough for typical vaults (>50 notes/sec). GPU is only relevant for bulk re-indexing of very large vaults.

### Health Check

A lightweight health check for container monitoring:

```yaml
# In docker-compose.yml
services:
  cortex:
    healthcheck:
      test: ["CMD", "uv", "run", "python", "-c", "import cortex; cortex.health_check()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s  # Allow time for model loading
```

The health check verifies: Python process is responsive, DuckDB file is accessible, vault path is mounted and readable.

---

## 7. Session-by-Session Implementation Guide

Each session below maps to a PRD session and includes specific technical deliverables.

### Session 1: Project Scaffolding, Vault Structure & Docker Setup

**Deliverables:**
- `pyproject.toml` with all dependencies
- `src/cortex/config.py` — Pydantic settings model
- `settings.yaml` — default config
- `vault/` directory with all folders
- `vault/_templates/` with templates for each note type
- `justfile` with commands: `dev`, `test`, `index-rebuild`, `serve`, `docker-build`, `docker-up`, `docker-down`
- `Dockerfile` — multi-stage build (dependencies → model download → runtime)
- `docker-compose.yml` — service definition with vault bind mount and data named volume
- `docker-compose.gpu.yml` — GPU override file for NVIDIA acceleration
- `.dockerignore` — exclude `data/`, `vault/`, `__pycache__/`, `.venv/`, `*.pyc`
- `scripts/docker-entrypoint.sh` — first-run vault scaffolding and index building
- MCP config snippet for Claude Code (`README.md` or separate `mcp-config.json` example)

**Dependencies to install (via uv):**
```
mcp (FastMCP), python-frontmatter, mistune, duckdb,
lancedb, sentence-transformers, networkx, watchdog, pydantic-settings,
pytest, pytest-asyncio
```

**Exit criteria:** `just dev` starts without errors. Templates render correctly. `docker compose build` completes. `docker compose run --rm cortex uv run python -c "import cortex"` succeeds. Docker image size is < 3GB.

---

### Session 2: Markdown Parser & Metadata Extractor

**Deliverables:**
- `src/cortex/vault/parser.py` — `parse_note(path) -> Note`
- `src/cortex/vault/manager.py` — basic `VaultManager` (read operations)
- `tests/test_vault/test_parser.py` — 10+ test cases

**Key behaviors to test:**
- Frontmatter extraction (valid YAML, missing fields, empty frontmatter)
- Wikilink extraction (`[[note title]]`, `[[note title|alias]]`)
- Tag extraction (inline `#tag` and frontmatter `tags:`)
- Markdown link extraction `[text](url)`
- Edge cases: empty files, binary files, no frontmatter

**Exit criteria:** All parser tests pass. Can parse a sample vault of 20 notes.

---

### Session 3: Capture Commands & Review-Before-Create Flow

**Deliverables:**
- `src/cortex/capture/draft.py` — `NoteDraft` dataclass and `DraftManager` class
- `src/cortex/vault/templates.py` — template rendering
- `src/cortex/capture/thought.py`, `task.py`, `link.py`, `note.py` — all producing drafts
- `src/cortex/vault/manager.py` — add write operations (only called on approval)
- `tests/test_capture/` — test each capture type AND the draft lifecycle

**Key behaviors:**
- All capture commands produce a `NoteDraft` in memory — nothing touches disk until approved
- `NoteDraft.render_preview()` returns a clean formatted string for Claude to show the user
- `DraftManager.update_draft()` applies partial edits (title, tags, content, folder) and returns a new preview
- `DraftManager.approve_draft()` writes the note to vault, indexes it, and updates the graph
- `DraftManager.reject_draft()` discards the draft cleanly
- Frontmatter includes all required fields (id, title, type, created, tags)
- Task captures include `due_date` and `priority` fields
- Link captures extract URL metadata (title from HTML if possible, or just domain)
- File naming: `{date}-{type}-{short-hash}-{slug}.md` (short hash ensures uniqueness)

**Exit criteria:** Full draft lifecycle works: create draft → preview → edit → approve → file exists on disk. Also: create draft → reject → no file created. All 5 note types produce valid Obsidian notes after approval.

---

### Session 4: Lexical Index (DuckDB)

**Deliverables:**
- `src/cortex/index/lexical.py` — `LexicalIndex` class
- `src/cortex/index/manager.py` — `IndexManager` (orchestrates both indexes)
- `tests/test_index/test_lexical.py`

**Key behaviors:**
- Full-text search with BM25 scoring
- Filter by note_type, tags, date range, status
- Index a vault of 100 notes in < 2 seconds
- Incremental updates (add/update/remove single notes)
- Rebuild from scratch

**Exit criteria:** Can search a test vault and get relevant results ranked by BM25.

---

### Session 5: Embedding Pipeline & Vector Store (LanceDB)

**Deliverables:**
- `src/cortex/index/models.py` — embedding model wrapper
- `src/cortex/index/semantic.py` — `SemanticIndex` class
- `tests/test_index/test_semantic.py`

**Key behaviors:**
- Load `nomic-embed-text` model on init (768-dim vectors)
- Semantic-boundary chunking: split on paragraph boundaries first, then sentence boundaries. Target ~300 tokens, max 500. Use nomic tokenizer for counting.
- No note-level embeddings — boost note score in fusion if multiple chunks rank highly
- Semantic search returns results with cosine similarity scores
- Metadata filtering (note_type, tags)

**Exit criteria:** Can embed a test vault. Semantic search for "machine learning" returns ML-related notes.

---

### Session 6: Hybrid Search & Fusion

**Deliverables:**
- `src/cortex/query/fusion.py` — RRF implementation
- `src/cortex/query/pipeline.py` — `QueryPipeline` orchestrator
- `src/cortex/query/context.py` — `ContextAssembler`
- `tests/test_query/`

**Key behaviors:**
- Pipeline runs all three retrieval systems (lexical, semantic, graph) in parallel — no routing classification
- RRF merges results from all three systems with correct scoring
- Context assembler produces a structured block with excerpts, metadata, scores
- Pipeline returns `QueryResult` with explanation of which systems contributed

**Exit criteria:** End-to-end query from string → structured context block. All three retrieval systems contribute.

---

### Session 7: FastMCP Server Integration

**Deliverables:**
- `src/cortex/mcp/server.py` — FastMCP server with tool definitions
- `src/cortex/mcp/tools.py` — tool implementations calling services
- `src/cortex/cli.py` — CLI with `serve`, `stdio`, `install`, `uninstall`, `restart`, `status` commands
- `src/cortex/main.py` — backward-compat entry point (also supports `--http` flag)
- `src/cortex/__main__.py` — enables `python -m cortex`
- `pyproject.toml` `[project.scripts]` entry: `cortex = "cortex.cli:cli"`
- LaunchAgent support for macOS (`com.cortex.mcp-server`)

**Key behaviors:**
- `cortex serve` runs the server on `127.0.0.1:8757` via streamable-http (multi-client)
- `cortex stdio` runs in stdio mode (single client, for Docker or testing)
- `cortex install` writes LaunchAgent + configures Claude Code and Claude Desktop MCP
- `cortex restart` restarts the server (picks up code changes in dev mode)
- FastMCP server starts and registers tools via decorators
- Claude Code and Claude Desktop can discover tools (`capture_thought`, `search_vault`, etc.)
- Capture tools create drafts and return previews (never write directly)
- Approve/update/reject tools manage the draft lifecycle
- Search tools run the query pipeline (all three systems in parallel) and return structured context
- Error handling (vault not found, index not built, etc.)
- Works identically whether invoked via `uv run cortex` (bare metal) or `docker compose run --rm -i cortex` (Docker)

**Exit criteria:** Claude Code can call `capture_thought`, `update_draft`, `approve_draft`, and `search_vault` successfully — tested both via bare-metal `uv run` and via Docker.

---

### Session 8: Knowledge Graph (NetworkX)

**Deliverables:**
- `src/cortex/graph/builder.py` — vault → NetworkX MultiDiGraph construction
- `src/cortex/graph/manager.py` — `GraphManager` class with GraphML persistence
- `src/cortex/graph/queries.py` — common query patterns using NetworkX algorithms
- `tests/test_graph/`

**Key behaviors:**
- Build `nx.MultiDiGraph` from vault: notes become nodes, wikilinks become LINKS_TO edges
- Phase 1: Note nodes + Project nodes only; extract from frontmatter
- Edges carry `rel_type` attribute (LINKS_TO, BELONGS_TO_PROJECT for Phase 1)
- Persist graph to `data/graph/graph.graphml` after mutations; load on startup
- Neighbor queries via `nx.bfs_edges` (1-hop, 2-hop)
- Path queries via `nx.shortest_path`
- Cluster queries via `nx.ego_graph` (subgraph around a node)

**Exit criteria:** Graph built from test vault, persisted to GraphML, reloaded correctly. Can query neighbors and find paths.

---

### Session 9: Retrieval Eval Framework

**Deliverables:**
- `evals/golden_dataset.json` — 50+ annotated query → expected-results pairs
- `evals/harness.py` — `EvalHarness` class that runs queries and checks assertions
- `evals/metrics.py` — MRR@10, Precision@5, NDCG@10 implementations
- `evals/snapshots/` — directory for versioned score snapshots
- `justfile` updated: `just eval` command

**Key behaviors:**
- Golden dataset covers all query categories: keyword, semantic, relational, temporal, hybrid
- Harness executes each case against a test vault with known content
- Metrics computed per-case and aggregated
- Results saved as JSON snapshot with timestamp for regression tracking
- `compare_to()` method flags any metric drop > 0.05

**Exit criteria:** Eval suite runs end-to-end. Baseline scores established and saved as snapshot v0. MRR@10, Precision@5, and NDCG@10 all computed.

---

### Session 10: Heuristic Reranking & Quality Tuning

**Deliverables:**
- `src/cortex/query/reranker.py` — heuristic reranking (recency, note type, inbound links, active status)
- Updated `pipeline.py` — integrate graph results + heuristic reranking
- Updated eval snapshot (v1)

**Key behaviors:**
- Heuristic scoring: boost recent notes, active notes, notes with more inbound links, high-value types
- Reranking improves result order vs. fusion-only
- Graph results contribute to all queries (neighbors, paths, project scope)
- Result explanations include: matched_by (lexical/semantic/graph), score, rank change
- Fusion weights and heuristic parameters tuned using eval framework — iterate until scores improve
- Cross-encoder deferred to Phase 2 after validating heuristic approach

**Exit criteria:** Run eval, compare v1 snapshot against v0 baseline. MRR@10 must improve or stay equal. No metric may regress by > 0.05.

---

### Session 11: Note Lifecycle Management

**Deliverables:**
- `src/cortex/lifecycle/manager.py` — `LifecycleManager` class
- `src/cortex/lifecycle/staleness.py` — staleness detection heuristics
- Updated `pipeline.py` — status-based score multipliers
- Updated `context.py` — supersession annotations
- MCP tools: `edit_note`, `archive_note`, `unarchive_note`, `supersede_note`, `detect_stale`
- `tests/test_lifecycle/` — full lifecycle test suite
- Lifecycle-specific eval cases added to `golden_dataset.json`
- Updated eval snapshot (v2)

**Key behaviors:**
- Edit flow: find note → load → generate draft with diff → user reviews → approve → re-index all 3 stores
- Archive flow: set `status: archived`, `archived_date`, apply 0.3x score multiplier in pipeline
- Supersede flow: bidirectional frontmatter links, `SUPERSEDES` graph edge, 0.2x multiplier, context annotation
- Staleness detection: identify orphan notes (no inbound links), stale notes (not modified in N days)
- Index consistency: after any mutation, DuckDB + LanceDB + NetworkX must all reflect the change
- Re-indexing: old embeddings are deleted and replaced (not appended) after edits

**Index consistency test pattern:**
```python
def test_edit_consistency():
    # 1. Create note about "Redis caching"
    # 2. Verify it appears in search for "Redis"
    # 3. Edit note to say "Memcached caching"
    # 4. Verify search for "Redis" does NOT return this note
    # 5. Verify search for "Memcached" DOES return this note
    # 6. Verify DuckDB row has new content
    # 7. Verify LanceDB vectors are new (cosine sim to old embedding < 0.9)
    # 8. Verify NetworkX node attributes updated
```

**Exit criteria:** All lifecycle flows work end-to-end. Eval suite v2 passes — supersession_correctness = 100%, archival_penalty_accuracy ≥ 95%, edit_consistency = 100%. No regression on retrieval metrics from v1.

---

### Session 12: Workflows

**Deliverables:**
- `src/cortex/workflow/inbox.py` — process inbox items
- `src/cortex/workflow/review.py` — weekly/monthly review
- `src/cortex/workflow/summarize.py` — source summarization
- `src/cortex/workflow/staleness_review.py` — guided staleness triage
- MCP tools for workflows

**Key behaviors:**
- `process_inbox`: lists inbox items, suggests categorization (which folder, which tags)
- `generate_review`: aggregates captures, tasks, and notes from time period
- `summarize_source`: extracts key points from a source note
- `staleness_review`: runs staleness detection, presents candidates with suggested actions (archive/review/merge)

**Exit criteria:** Weekly review generates a meaningful markdown document from a week of test data. Staleness review correctly identifies planted stale notes in test vault.

---

### Session 13: File Watching & Incremental Updates

**Deliverables:**
- `src/cortex/vault/watcher.py` — watchdog-based file watcher
- Updated index/graph/lifecycle managers for incremental operations
- Performance benchmarks

**Key behaviors:**
- Detect file create/modify/delete in vault
- Trigger index updates within 5 seconds of file change
- Handle rapid changes (debouncing)
- Handle Obsidian's temp file patterns (`.md~`, sync conflicts)
- Edits made in Obsidian directly trigger the same re-indexing as `edit_note` MCP tool
- **Conflict resolution:** Obsidian always wins — external changes (from MCP tools or elsewhere) are detected by the file watcher, triggering a re-index. If a draft exists for a note that was modified externally, the draft is discarded (the underlying note's modified timestamp changed).

**Exit criteria:** Edit a note in Obsidian → search reflects the change within 5 seconds. Run eval to confirm no regression.

---

### Session 14: Polish, Documentation & Docker Hardening

**Deliverables:**
- `README.md` — setup guide with both bare-metal and Docker quick-start paths
- `settings.yaml` — documented configuration (including Docker env var overrides)
- Error handling audit
- Setup script (`just setup` for bare metal, `just docker-build` for Docker)
- Docker quick-start guide: clone → `docker compose up` → configure Claude Code → working
- `src/cortex/health.py` — health check function for Docker monitoring
- Docker troubleshooting section (volume permissions, model cache, GPU setup)
- Document git-based backup setup for vault and derived data
- Final eval run (v_final) — must meet all success metrics, run inside Docker container

**Exit criteria:** A new user can clone, run `docker compose up`, configure Claude Code with the Docker MCP config snippet, and start using the system within 10 minutes. Bare-metal path (`just setup && just serve`) also works. Final eval snapshot meets all targets in both environments.

---

## 8. Testing Strategy

| Level | Scope | Tools |
|---|---|---|
| Unit | Individual parsers, indexers, query components | pytest |
| Integration | Query pipeline end-to-end, capture → index flow | pytest + temp vault fixtures |
| Lifecycle | Edit/archive/supersede flows, index consistency | pytest + lifecycle-specific assertions |
| System | Claude Code → MCP → full pipeline → response | Manual + scripted MCP calls |
| Eval | Retrieval relevance, lifecycle correctness, regression | Custom eval harness (see §8a) |

**Test vault fixture:** A reusable set of 50 notes across all types, with known relationships, to validate retrieval quality consistently. Includes notes in all lifecycle states (active, archived, superseded) with known supersession chains.

---

## 8a. Retrieval Eval Framework

This is the quality gate for the entire system. Every change to retrieval, indexing, scoring, or lifecycle logic must pass the eval suite before being considered done.

### Golden Dataset

A JSON file (`evals/golden_dataset.json`) containing annotated query-expectation pairs:

```json
{
  "version": "1.0",
  "cases": [
    {
      "id": "q001",
      "query": "caching strategies for distributed systems",
      "category": "semantic",
      "expected_notes": ["note-memcached-strategy", "note-redis-patterns"],
      "expected_not": ["note-redis-old-superseded"],
      "min_rank": {"note-memcached-strategy": 3},
      "tags": ["retrieval", "ranking"]
    },
    {
      "id": "q002",
      "query": "caching strategies for distributed systems",
      "category": "lifecycle-supersession",
      "description": "Superseded Redis note must rank below its replacement",
      "setup": {
        "supersede": {"old": "note-redis-patterns", "new": "note-memcached-strategy"}
      },
      "assertions": [
        {"type": "rank_higher", "note": "note-memcached-strategy", "than": "note-redis-patterns"},
        {"type": "has_annotation", "note": "note-redis-patterns", "contains": "Superseded by"}
      ],
      "tags": ["lifecycle", "supersession"]
    },
    {
      "id": "q003",
      "query": "old database migration approach",
      "category": "lifecycle-archival",
      "description": "Archived note should appear but rank lower than active notes",
      "setup": {
        "archive": ["note-db-migration-v1"]
      },
      "assertions": [
        {"type": "present_in_results", "note": "note-db-migration-v1"},
        {"type": "score_below", "note": "note-db-migration-v1", "threshold": 0.5}
      ],
      "tags": ["lifecycle", "archival"]
    },
    {
      "id": "q004",
      "query": "vector databases",
      "category": "lifecycle-edit",
      "description": "After editing a note, search must return the new content, not the old",
      "setup": {
        "edit": {"note": "note-vectordb", "old_content": "FAISS is best", "new_content": "LanceDB is best"}
      },
      "assertions": [
        {"type": "content_contains", "note": "note-vectordb", "text": "LanceDB"},
        {"type": "content_not_contains", "note": "note-vectordb", "text": "FAISS is best"}
      ],
      "tags": ["lifecycle", "edit", "index-consistency"]
    }
  ]
}
```

### Eval Harness

```python
# evals/harness.py

class EvalHarness:
    """Run retrieval evals against a test vault and score the results."""

    def __init__(self, pipeline: QueryPipeline, lifecycle: LifecycleManager,
                 dataset_path: Path):
        self._pipeline = pipeline
        self._lifecycle = lifecycle
        self._dataset = self._load_dataset(dataset_path)

    def run_all(self) -> EvalReport:
        """Run all eval cases, return aggregated scores."""
        ...

    def run_tagged(self, tags: list[str]) -> EvalReport:
        """Run only cases matching given tags (e.g., ['lifecycle'])."""
        ...

    def _execute_case(self, case: EvalCase) -> CaseResult:
        """
        1. Apply any setup mutations (archive, supersede, edit)
        2. Run the query through the pipeline
        3. Check all assertions
        4. Return pass/fail + details
        """
        ...

@dataclass
class EvalReport:
    timestamp: datetime
    total_cases: int
    passed: int
    failed: int
    metrics: dict               # MRR@10, Precision@5, NDCG@10
    lifecycle_metrics: dict     # supersession_correctness, archival_penalty_accuracy, edit_consistency
    failed_cases: list[CaseResult]

    def compare_to(self, previous: "EvalReport") -> RegressionReport:
        """Compare this run against a previous snapshot. Flag regressions."""
        ...

    def save_snapshot(self, path: Path) -> None:
        """Save as versioned JSON for historical tracking."""
        ...
```

### Metrics

| Metric | What it measures | Target |
|---|---|---|
| **MRR@10** | Mean Reciprocal Rank — how high the first relevant result ranks | ≥ 0.7 |
| **Precision@5** | Fraction of top-5 results that are relevant | ≥ 0.6 |
| **NDCG@10** | Normalized Discounted Cumulative Gain — ranking quality | ≥ 0.65 |
| **Supersession correctness** | % of cases where the newer note ranks above the superseded one | 100% |
| **Archival penalty accuracy** | % of cases where archived notes score below active notes for same query | ≥ 95% |
| **Edit consistency** | % of cases where edited content is reflected in results within 5s | 100% |
| **Index agreement** | All three indexes (DuckDB, LanceDB, NetworkX) agree on note count and status | 100% |

### Regression Detection

After every change to retrieval, lifecycle, or scoring logic:

1. Run `just eval` (which invokes the harness).
2. Compare against the most recent snapshot in `evals/snapshots/`.
3. If any metric drops by more than 0.05, or any lifecycle assertion fails, the change is flagged as a regression.
4. The `run_eval` MCP tool lets you trigger this from Claude Code and see results inline.

### How to Add New Eval Cases

When you add a new feature or fix a bug:

1. Write a new case in `golden_dataset.json` that would have caught the issue.
2. Verify the case fails before your fix and passes after.
3. Run the full suite to confirm no regressions.
4. Commit the updated dataset alongside your code change.

---

## 9. Performance Targets

| Metric | Target | Measurement |
|---|---|---|
| Cold start (index build, 500 notes) | < 60 seconds | Timer in index rebuild |
| Capture-to-indexed | < 5 seconds | File watcher latency test |
| Edit-to-reindexed | < 5 seconds | All 3 indexes refreshed after edit |
| Query latency (hybrid) | < 3 seconds | End-to-end timer |
| Embedding throughput | > 50 notes/second | Batch embedding benchmark |
| Memory usage (serving) | < 500 MB | Process monitoring |
| Vault size support | 1,000+ notes | Load test |
| Docker image build time | < 5 minutes (fresh) | `time docker compose build` |
| Docker cold start (first run) | < 90 seconds | Timer from `docker compose up` to first MCP response (includes model load + index build for small vault) |
| Docker warm start | < 15 seconds | Timer from `docker compose up` to first MCP response (indexes exist, model cached) |

---

## 10. Risk & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Embedding model too slow on CPU | Medium | High | Use `nomic-embed-text` (trained for retrieval); batch operations; lazy loading |
| NetworkX graph too large for memory | Low | Medium | At ~10K+ nodes, consider migrating to SQLite-backed graph or edge-list storage; graph is always rebuildable from vault |
| FastMCP protocol changes | Low | Medium | Wrap MCP layer thinly; core logic is MCP-independent |
| DuckDB FTS limitations | Low | Low | Tantivy-py as fallback for more advanced FTS |
| LanceDB compatibility issues | Low | Medium | ChromaDB as fallback (also embedded) |
| Index inconsistency after failed edit | Medium | High | Vault file is source of truth; write vault first, then indexes; `rebuild_index` can always recover; log inconsistencies for repair |
| Stale embeddings after edit (old vectors not deleted) | Medium | High | LanceDB reindex deletes by note_id before inserting; unit test verifies old vectors are gone |
| Supersession chains get long | Low | Low | Only display immediate supersessor in annotations; graph can traverse the full chain if needed |
| GraphML file corruption or loss | Low | Medium | Vault is source of truth; graph is always fully rebuildable via `rebuild_index` |
| Docker image too large (embedding model) | Medium | Low | Multi-stage build caches model in dedicated layer; image ~2.5GB with model, acceptable trade-off for zero-setup |
| Docker volume permissions (vault bind mount) | Medium | Medium | Entrypoint script checks permissions; document `--user` flag for non-root runs; default to running as non-root user in Dockerfile |
| Docker stdio transport latency | Low | Low | stdio overhead is negligible (<1ms per message); no HTTP layer = minimal overhead vs bare metal |
| File watcher inside Docker container | Medium | Medium | watchdog uses inotify on Linux; works natively with bind mounts on Linux; macOS/Windows Docker may have polling fallback — document and test |

---

*End of TDD*
