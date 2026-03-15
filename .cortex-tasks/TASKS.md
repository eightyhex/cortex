# Cortex — Atomic Task Plan

> Each task is self-contained: an agent reads this file, picks the next `pending` task, completes it, updates PROGRESS.md, and exits. Tasks are ordered by dependency — complete them sequentially.

---

## Session 1: Project Scaffolding, Vault Structure & Docker Setup

### Task 1.1 — Pydantic Config Module
**Status:** `done`
**File:** `src/cortex/config.py`
**Depends on:** nothing (first task)

**Description:** Implement the Pydantic Settings model that loads `settings.yaml` and environment variable overrides. This is the foundation every other module depends on.

**Acceptance Criteria:**
- [ ] `CortexConfig` class using `pydantic-settings` with nested models for vault, index, embeddings, search, lifecycle, draft, and mcp sections
- [ ] Loads from `settings.yaml` (or `settings.example.yaml` as fallback) via `yaml` parsing
- [ ] Environment variable overrides work (e.g., `CORTEX_VAULT_PATH`)
- [ ] `config.vault.path` returns a `Path` object
- [ ] All fields have sensible defaults matching `settings.example.yaml`
- [ ] `tests/test_config.py` with 3+ tests: default loading, env override, missing file fallback

---

### Task 1.2 — Vault Directory Scaffolding
**Status:** `done`
**File:** `src/cortex/vault/manager.py` (partial — `scaffold_vault()` function)
**Depends on:** Task 1.1

**Description:** Implement vault directory creation — the function that ensures all vault folders exist.

**Acceptance Criteria:**
- [ ] `scaffold_vault(vault_path: Path)` creates all 9 folders: `00-inbox/`, `01-daily/`, `02-tasks/`, `10-sources/`, `20-concepts/`, `30-permanent/`, `40-projects/`, `50-reviews/`, `_templates/`
- [ ] Idempotent: calling twice doesn't error
- [ ] Copies template files from `vault.example/_templates/` into `{vault_path}/_templates/` if they don't already exist
- [ ] `tests/test_vault/test_scaffold.py` with 2+ tests: fresh scaffold, idempotent re-scaffold

---

### Task 1.3 — Note Templates Module
**Status:** `done`
**File:** `src/cortex/vault/templates.py`
**Depends on:** Task 1.1

**Description:** Template rendering for each note type. Given a note type and metadata, produce the full markdown string (frontmatter + body).

**Acceptance Criteria:**
- [ ] `render_template(note_type: str, title: str, tags: list[str], content: str, **kwargs) -> str` returns valid YAML frontmatter + markdown body
- [ ] Supports all note types: inbox, daily, task, source, concept, permanent, project, review
- [ ] Generated frontmatter includes: `id` (UUID), `title`, `type`, `created` (ISO datetime), `modified` (ISO datetime), `tags`, `status` (default `active`)
- [ ] Task type includes `due_date`, `priority` fields
- [ ] Source type includes `source_url` field
- [ ] Output is valid Obsidian-compatible markdown (YAML frontmatter between `---` delimiters)
- [ ] `tests/test_vault/test_templates.py` with 5+ tests covering each note type

---

### Task 1.4 — Dockerfile & Docker Compose
**Status:** `done`
**Files:** `Dockerfile`, `docker-compose.yml`, `docker-compose.gpu.yml`, `scripts/docker-entrypoint.sh`
**Depends on:** Task 1.1

**Description:** Create the Docker setup for one-command deployment.

**Acceptance Criteria:**
- [ ] Multi-stage `Dockerfile`: deps stage → model download stage → runtime stage
- [ ] `docker-compose.yml` with vault bind mount (`CORTEX_VAULT_PATH` env var, default `./vault`), named `cortex-data` volume for `data/`, `stdin_open: true`, healthcheck
- [ ] `docker-compose.gpu.yml` override with NVIDIA GPU support
- [ ] `scripts/docker-entrypoint.sh`: scaffolds vault if empty, builds indexes if missing, warms up embedding model, then `exec "$@"`
- [ ] `.dockerignore` excludes `data/`, `vault/`, `__pycache__/`, `.venv/`, `*.pyc`, `.git/`
- [ ] Entrypoint script is executable (`chmod +x`)

---

### Task 1.5 — Justfile Dev Commands
**Status:** `done`
**File:** `justfile`
**Depends on:** Task 1.1, 1.4

**Description:** Update the justfile with all development and Docker commands.

**Acceptance Criteria:**
- [ ] Commands: `dev` (run MCP server locally), `test` (pytest), `lint` (ruff + black check), `format` (ruff fix + black), `index-rebuild`, `eval`, `docker-build`, `docker-up`, `docker-down`, `docker-shell`
- [ ] `just test` runs `uv run pytest`
- [ ] `just docker-build` runs `docker compose build`
- [ ] `just dev` runs `uv run python -m cortex.main`

---

## Session 2: Markdown Parser & Metadata Extractor

### Task 2.1 — Frontmatter Parser
**Status:** `done`
**File:** `src/cortex/vault/parser.py`
**Depends on:** Task 1.1

**Description:** Parse markdown files with YAML frontmatter into `Note` dataclass instances.

**Acceptance Criteria:**
- [ ] `Note` dataclass with fields: `id`, `title`, `note_type`, `path`, `content`, `frontmatter`, `created`, `modified`, `tags`, `links`, `status`, `supersedes`, `superseded_by`, `archived_date`
- [ ] `parse_note(path: Path) -> Note` extracts frontmatter via `python-frontmatter` and populates the `Note` dataclass
- [ ] Handles missing frontmatter gracefully (returns Note with defaults)
- [ ] Handles missing fields in frontmatter (uses defaults: status=`active`, tags=`[]`)
- [ ] Handles empty files without crashing
- [ ] `tests/test_vault/test_parser.py` with 6+ tests: valid note, missing frontmatter, missing fields, empty file, all note types, unicode content

---

### Task 2.2 — Link & Tag Extractor
**Status:** `done`
**File:** `src/cortex/vault/parser.py` (extend)
**Depends on:** Task 2.1

**Description:** Extract wikilinks, markdown links, and inline tags from note content.

**Acceptance Criteria:**
- [ ] `extract_wikilinks(content: str) -> list[str]` — extracts `[[target]]` and `[[target|alias]]` (returns target only)
- [ ] `extract_markdown_links(content: str) -> list[tuple[str, str]]` — extracts `[text](url)` pairs
- [ ] `extract_inline_tags(content: str) -> list[str]` — extracts `#tag` from body text (not from code blocks)
- [ ] `Link` dataclass with fields: `source_id`, `target_id`, `target_title`, `link_type`
- [ ] `parse_note()` now populates `note.links` with extracted wikilinks
- [ ] `parse_note()` merges inline tags with frontmatter tags (deduplicated)
- [ ] `tests/test_vault/test_links.py` with 8+ tests: wikilinks, aliased wikilinks, markdown links, inline tags, mixed content, no links, tags in code blocks (should be excluded)

---

### Task 2.3 — VaultManager Read Operations
**Status:** `done`
**File:** `src/cortex/vault/manager.py`
**Depends on:** Task 2.1, 2.2

**Description:** Implement the read-side of VaultManager — listing and retrieving notes from the vault.

**Acceptance Criteria:**
- [ ] `VaultManager.__init__(self, vault_path: Path, config: CortexConfig)` — stores path, verifies vault exists
- [ ] `get_note(self, note_id: str) -> Note` — finds note by UUID (scans frontmatter)
- [ ] `get_note_by_path(self, path: Path) -> Note` — parses note at given path
- [ ] `list_notes(self, folder: str = None, note_type: str = None) -> list[Note]` — lists all notes, optionally filtered
- [ ] `scan_vault(self) -> list[Note]` — parses all `.md` files in vault (excludes `_templates/`)
- [ ] `tests/test_vault/test_manager.py` with 5+ tests using a temp vault fixture with sample notes

---

## Session 3: Capture Commands & Review-Before-Create Flow

### Task 3.1 — NoteDraft & DraftManager
**Status:** `done`
**File:** `src/cortex/capture/draft.py`
**Depends on:** Task 1.3, 2.3

**Description:** Implement the draft system — in-memory draft generation with file-based persistence.

**Acceptance Criteria:**
- [ ] `NoteDraft` dataclass with fields: `draft_id`, `note_type`, `title`, `content`, `frontmatter`, `target_folder`, `target_filename`, `created_at`
- [ ] `NoteDraft.render_preview() -> str` — formatted preview string showing title, type, tags, folder, and body
- [ ] `NoteDraft.render_markdown() -> str` — full markdown (frontmatter + body) ready for disk write
- [ ] `NoteDraft.apply_edits(edits: dict) -> NoteDraft` — returns new draft with changes (supports title, content, tags, folder changes)
- [ ] `DraftManager.__init__(self, drafts_dir: Path)` — creates dir, runs cleanup
- [ ] `DraftManager.create_draft(...)` → persists JSON to `data/drafts/{draft_id}.json`, returns `NoteDraft`
- [ ] `DraftManager.get_draft(draft_id)` → loads from JSON file
- [ ] `DraftManager.update_draft(draft_id, edits)` → applies edits, saves updated JSON
- [ ] `DraftManager.reject_draft(draft_id)` → deletes the JSON file
- [ ] `DraftManager._cleanup_stale_drafts()` → deletes files older than 24h
- [ ] File naming: `{date}-{type}-{short-hash}-{slug}.md` where short-hash = first 4 chars of UUID hex
- [ ] `tests/test_capture/test_draft.py` with 8+ tests: create, preview, edit, reject, cleanup, JSON round-trip

---

### Task 3.2 — VaultManager Write Operations
**Status:** `done`
**File:** `src/cortex/vault/manager.py` (extend)
**Depends on:** Task 3.1

**Description:** Add write operations to VaultManager — creating and updating notes on disk.

**Acceptance Criteria:**
- [ ] `create_note(self, draft: NoteDraft) -> Note` — writes the rendered markdown to `{vault_path}/{target_folder}/{target_filename}`, returns parsed `Note`
- [ ] `update_note(self, note_id: str, content: str = None, metadata: dict = None) -> Note` — overwrites note file, updates `modified` timestamp
- [ ] Ensures parent directory exists before writing
- [ ] `tests/test_vault/test_manager_write.py` with 4+ tests: create from draft, update content, update metadata, verify file on disk

---

### Task 3.3 — Capture Commands
**Status:** `done`
**Files:** `src/cortex/capture/thought.py`, `task.py`, `link.py`, `note.py`
**Depends on:** Task 3.1, 3.2

**Description:** Implement the four capture commands — each produces a `NoteDraft` (nothing touches disk).

**Acceptance Criteria:**
- [ ] `capture_thought(content: str, tags: list[str] = None) -> NoteDraft` — creates inbox note draft
- [ ] `add_task(title: str, description: str = None, due_date: str = None, priority: str = None, tags: list[str] = None) -> NoteDraft` — creates task note draft
- [ ] `save_link(url: str, title: str = None, description: str = None, tags: list[str] = None) -> NoteDraft` — creates source note draft with URL metadata
- [ ] `create_note(note_type: str, title: str, content: str, tags: list[str] = None) -> NoteDraft` — generic note creation (concept, permanent, project)
- [ ] All functions use `DraftManager.create_draft()` internally
- [ ] All functions use templates from Task 1.3
- [ ] `tests/test_capture/test_commands.py` with 6+ tests: one per command + edge cases (no tags, no due date)

---

### Task 3.4 — DraftManager.approve_draft Integration
**Status:** `done`
**File:** `src/cortex/capture/draft.py` (extend)
**Depends on:** Task 3.2, 3.3

**Description:** Wire up `approve_draft()` to actually write to the vault. (Index/graph integration will come later — for now just write the file.)

**Acceptance Criteria:**
- [ ] `DraftManager.approve_draft(draft_id: str, vault: VaultManager) -> Note` — calls `vault.create_note(draft)`, deletes draft file, returns `Note`
- [ ] After approval, the `.md` file exists on disk at the correct path
- [ ] After approval, the draft JSON file is deleted
- [ ] `tests/test_capture/test_approve.py` with 3+ tests: approve creates file, approve deletes draft, approve returns valid Note

---

## Session 4: Lexical Index (DuckDB)

### Task 4.1 — LexicalIndex Core
**Status:** `done`
**File:** `src/cortex/index/lexical.py`
**Depends on:** Task 2.1

**Description:** DuckDB-based full-text search index.

**Acceptance Criteria:**
- [ ] `LexicalIndex.__init__(self, db_path: Path)` — creates/opens DuckDB database, creates `notes` table if not exists (schema from TDD §4.4)
- [ ] `index_note(self, note: Note) -> None` — upserts note into the table (INSERT or REPLACE)
- [ ] `remove_note(self, note_id: str) -> None` — deletes note from table
- [ ] `rebuild(self, notes: list[Note]) -> None` — drops and recreates the table + FTS index, inserts all notes
- [ ] `search(self, query: str, limit: int = 20, filters: dict = None) -> list[SearchResult]` — BM25 full-text search with optional filters (note_type, tags, status, date_range)
- [ ] `SearchResult` dataclass with: `note_id`, `title`, `score`, `snippet`, `note_type`, `path`
- [ ] Tags stored as both `VARCHAR[]` (filtering) and `tags_text VARCHAR` (FTS)
- [ ] `tests/test_index/test_lexical.py` with 8+ tests: index a note, search by keyword, search with filters, rebuild, remove, empty results, BM25 ranking

---

### Task 4.2 — IndexManager Skeleton
**Status:** `done`
**File:** `src/cortex/index/manager.py`
**Depends on:** Task 4.1

**Description:** Create IndexManager that orchestrates both indexes (semantic will be added next session).

**Acceptance Criteria:**
- [ ] `IndexManager.__init__(self, config: CortexConfig)` — initializes `LexicalIndex`
- [ ] `index_note(self, note: Note) -> None` — delegates to lexical index (and later semantic)
- [ ] `remove_note(self, note_id: str) -> None` — delegates to lexical index
- [ ] `reindex_note(self, note: Note) -> None` — remove + re-add
- [ ] `rebuild_all(self, notes: list[Note]) -> None` — full rebuild
- [ ] `tests/test_index/test_manager.py` with 3+ tests

---

## Session 5: Embedding Pipeline & Vector Store

### Task 5.1 — Embedding Model Wrapper
**Status:** `done`
**File:** `src/cortex/index/models.py`
**Depends on:** Task 1.1

**Description:** Wrapper around sentence-transformers for embedding generation.

**Acceptance Criteria:**
- [ ] `EmbeddingModel.__init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5")` — loads model
- [ ] `embed(self, text: str) -> list[float]` — returns 768-dim vector
- [ ] `embed_batch(self, texts: list[str]) -> list[list[float]]` — batch embedding
- [ ] `tokenize_count(self, text: str) -> int` — returns token count using the model's tokenizer
- [ ] Lazy model loading (load on first use, not on init)
- [ ] `tests/test_index/test_models.py` with 3+ tests: single embed, batch embed, dimension check (768)

---

### Task 5.2 — Semantic Boundary Chunker
**Status:** `done`
**File:** `src/cortex/index/chunker.py` (new file)
**Depends on:** Task 5.1

**Description:** Split notes into chunks at semantic boundaries (paragraphs, then sentences).

**Acceptance Criteria:**
- [ ] `chunk_note(note: Note, model: EmbeddingModel, target_tokens: int = 300, max_tokens: int = 500) -> list[Chunk]`
- [ ] `Chunk` dataclass: `chunk_id` (format: `{note_id}__chunk_{N}`), `note_id`, `text`, `index`
- [ ] Splits on paragraph boundaries (`\n\n`) first
- [ ] If a paragraph exceeds `max_tokens`, splits on sentence boundaries
- [ ] Each chunk is `target_tokens` ± reasonable margin
- [ ] Short notes (< target_tokens) become a single chunk
- [ ] `tests/test_index/test_chunker.py` with 5+ tests: short note, long note, paragraph split, sentence split, token counting

---

### Task 5.3 — SemanticIndex (LanceDB)
**Status:** `done`
**File:** `src/cortex/index/semantic.py`
**Depends on:** Task 5.1, 5.2

**Description:** LanceDB-based vector store for semantic search.

**Acceptance Criteria:**
- [ ] `SemanticIndex.__init__(self, db_path: Path, model: EmbeddingModel)` — creates/opens LanceDB
- [ ] `index_note(self, note: Note) -> None` — chunks the note, embeds chunks, stores in LanceDB
- [ ] `remove_note(self, note_id: str) -> None` — deletes all chunks for a note
- [ ] `rebuild(self, notes: list[Note]) -> None` — clears and rebuilds from scratch
- [ ] `search(self, query: str, limit: int = 20) -> list[SearchResult]` — embeds query, cosine similarity search
- [ ] LanceDB schema: `id`, `note_id`, `title`, `note_type`, `text`, `vector` (768-dim), `tags`, `created`
- [ ] `tests/test_index/test_semantic.py` with 6+ tests: index, search, remove, rebuild, semantic relevance (ML query returns ML notes)

---

### Task 5.4 — IndexManager Integration with SemanticIndex
**Status:** `done`
**File:** `src/cortex/index/manager.py` (extend)
**Depends on:** Task 5.3, 4.2

**Description:** Wire SemanticIndex into IndexManager so both indexes are updated together.

**Acceptance Criteria:**
- [ ] `IndexManager.__init__` now also initializes `SemanticIndex`
- [ ] `index_note()` updates both lexical and semantic indexes
- [ ] `remove_note()` removes from both
- [ ] `reindex_note()` removes + re-adds in both
- [ ] `rebuild_all()` rebuilds both
- [ ] `tests/test_index/test_manager.py` updated to verify both indexes are called

---

## Session 6: Hybrid Search & Fusion

### Task 6.1 — Reciprocal Rank Fusion
**Status:** `done`
**File:** `src/cortex/query/fusion.py`
**Depends on:** Task 4.1, 5.3

**Description:** Implement RRF to merge ranked result lists from multiple retrieval systems.

**Acceptance Criteria:**
- [ ] `reciprocal_rank_fusion(result_lists: list[list[SearchResult]], k: int = 60) -> list[SearchResult]` — merges results using RRF formula: `score(d) = sum(1 / (k + rank_i(d)))`
- [ ] Deduplicates by `note_id` (same note from different systems gets combined score)
- [ ] Returns results sorted by fused score descending
- [ ] Tracks which retrieval systems contributed to each result (for explainability)
- [ ] `tests/test_query/test_fusion.py` with 5+ tests: merge two lists, merge three lists, deduplication, empty list handling, score ordering

---

### Task 6.2 — Context Assembler
**Status:** `done`
**File:** `src/cortex/query/context.py`
**Depends on:** Task 6.1

**Description:** Format retrieval results into structured context for Claude.

**Acceptance Criteria:**
- [ ] `ContextAssembler.assemble(results: list[RankedResult], query: str, max_tokens: int = 4000) -> str`
- [ ] Output format: header (query + result count + retrieval methods), then per-result blocks (title, score, source system, excerpt, tags, links, created date)
- [ ] Truncates excerpts to fit within `max_tokens`
- [ ] Annotates superseded notes with warning: `⚠ This note was superseded by: [title] (id: xxx)`
- [ ] `tests/test_query/test_context.py` with 4+ tests: basic assembly, truncation, superseded annotation, empty results

---

### Task 6.3 — QueryPipeline
**Status:** `done`
**File:** `src/cortex/query/pipeline.py`
**Depends on:** Task 6.1, 6.2, 4.1, 5.3

**Description:** Orchestrate multi-stage retrieval: parallel search → fusion → context assembly.

**Acceptance Criteria:**
- [ ] `QueryPipeline.__init__(self, lexical: LexicalIndex, semantic: SemanticIndex, graph: GraphManager = None)`
- [ ] `async execute(self, query: str, limit: int = 10) -> QueryResult` — runs lexical and semantic search in parallel (graph is optional for now), fuses via RRF, assembles context
- [ ] `QueryResult` dataclass: `query`, `results: list[RankedResult]`, `context: str`, `explanation: str`
- [ ] `RankedResult` dataclass: `note_id`, `title`, `score`, `matched_by: list[str]`, `snippet`, `note_type`
- [ ] Status-based score multipliers applied after fusion: active=1.0, draft=0.8, archived=0.3, superseded=0.2
- [ ] `tests/test_query/test_pipeline.py` with 4+ tests: end-to-end query, status multipliers, explanation includes source systems

---

## Session 7: FastMCP Server Integration

### Task 7.1 — MCP Server Setup & Capture Tools
**Status:** `done`
**Files:** `src/cortex/mcp/server.py`, `src/cortex/main.py`
**Depends on:** Task 3.1, 3.3, 3.4

**Description:** Set up the FastMCP server with capture and draft lifecycle tools.

**Acceptance Criteria:**
- [ ] `src/cortex/mcp/server.py` creates a `FastMCP` server instance
- [ ] Tools registered via `@mcp.tool()` decorator: `capture_thought`, `add_task`, `save_link`, `create_note`
- [ ] Draft lifecycle tools: `approve_draft`, `update_draft`, `reject_draft`
- [ ] Capture tools return `{draft_id, preview, target_folder, target_filename}`
- [ ] Tool descriptions instruct Claude to show preview and ask for approval before approving
- [ ] `src/cortex/main.py` serves the MCP server via stdio transport
- [ ] `uv run python -m cortex.main` starts the server

---

### Task 7.2 — MCP Search & Admin Tools
**Status:** `done`
**File:** `src/cortex/mcp/server.py` (extend)
**Depends on:** Task 7.1, 6.3

**Description:** Add search and admin tools to the MCP server.

**Acceptance Criteria:**
- [ ] `search_vault(query: str, limit: int = 10, note_type: str = None)` tool — runs QueryPipeline, returns structured context
- [ ] `get_note(note_id: str)` tool — returns full note content
- [ ] `rebuild_index()` tool — triggers full index rebuild
- [ ] `vault_stats()` tool — returns note counts by type, index sizes, last rebuild time
- [ ] Error handling: returns clear error messages for common failures (vault not found, index not built)

---

## Session 8: Knowledge Graph (NetworkX)

### Task 8.1 — GraphManager & Graph Builder
**Status:** `done`
**Files:** `src/cortex/graph/manager.py`, `src/cortex/graph/builder.py`
**Depends on:** Task 2.1, 2.2

**Description:** Build the knowledge graph from vault notes using NetworkX with GraphML persistence.

**Acceptance Criteria:**
- [ ] `GraphManager.__init__(self, graph_path: Path)` — loads from GraphML or creates empty `nx.MultiDiGraph`
- [ ] `save(self) -> None` — writes to GraphML with backup (`.bak`)
- [ ] `build_from_vault(self, notes: list[Note]) -> None` — clears graph, adds Note nodes + Project nodes, LINKS_TO edges from wikilinks, BELONGS_TO_PROJECT from frontmatter
- [ ] `update_note(self, note: Note) -> None` — updates/adds a single note node and its edges
- [ ] `remove_note(self, note_id: str) -> None` — removes node and all connected edges
- [ ] Node attributes: `node_type` (note/project), `title`, `note_type`, `path`
- [ ] Edge attributes: `rel_type` (LINKS_TO / BELONGS_TO_PROJECT / SUPERSEDES)
- [ ] `tests/test_graph/test_manager.py` with 8+ tests: build, save/load round-trip, update node, remove node, edge creation

---

### Task 8.2 — Graph Queries
**Status:** `done`
**File:** `src/cortex/graph/queries.py`
**Depends on:** Task 8.1

**Description:** Implement graph query patterns for retrieval.

**Acceptance Criteria:**
- [ ] `get_neighbors(graph: nx.MultiDiGraph, note_id: str, depth: int = 1) -> list[str]` — BFS neighbors via `nx.bfs_edges`
- [ ] `find_path(graph: nx.MultiDiGraph, source_id: str, target_id: str) -> list[str]` — shortest path via `nx.shortest_path`
- [ ] `get_cluster(graph: nx.MultiDiGraph, note_id: str, max_nodes: int = 20) -> list[str]` — ego graph via `nx.ego_graph`
- [ ] `get_project_notes(graph: nx.MultiDiGraph, project_id: str) -> list[str]` — all notes linked to a project
- [ ] `graph_search(graph: nx.MultiDiGraph, note_ids: list[str], depth: int = 1) -> list[SearchResult]` — given seed note IDs from lexical/semantic, expand via graph and return neighbor notes as SearchResults
- [ ] `tests/test_graph/test_queries.py` with 6+ tests

---

### Task 8.3 — Graph Integration into QueryPipeline
**Status:** `done`
**File:** `src/cortex/query/pipeline.py` (extend)
**Depends on:** Task 8.2, 6.3

**Description:** Wire graph results into the hybrid search pipeline.

**Acceptance Criteria:**
- [ ] `QueryPipeline` now takes a `GraphManager` and uses `graph_search()` alongside lexical/semantic
- [ ] Graph search uses top-N note IDs from lexical+semantic as seeds, expands 1-hop neighbors
- [ ] Graph results included in RRF fusion with the other two systems
- [ ] `explanation` field in QueryResult now includes "graph" when graph contributes results
- [ ] `tests/test_query/test_pipeline.py` updated with graph integration test

---

## Session 9: Retrieval Eval Framework

### Task 9.1 — Eval Metrics
**Status:** `done`
**File:** `evals/metrics.py`
**Depends on:** Task 6.3

**Description:** Implement retrieval quality metrics.

**Acceptance Criteria:**
- [ ] `mrr_at_k(results: list[str], relevant: list[str], k: int = 10) -> float` — Mean Reciprocal Rank
- [ ] `precision_at_k(results: list[str], relevant: list[str], k: int = 5) -> float`
- [ ] `ndcg_at_k(results: list[str], relevant: list[str], k: int = 10) -> float` — Normalized Discounted Cumulative Gain
- [ ] All return 0.0 if no relevant results found
- [ ] `tests/test_evals/test_metrics.py` with 6+ tests: perfect ranking, no match, partial match, edge cases

---

### Task 9.2 — Golden Dataset & Eval Harness
**Status:** `done`
**Files:** `evals/golden_dataset.json`, `evals/harness.py`
**Depends on:** Task 9.1, 6.3

**Description:** Create the golden dataset and eval runner.

**Acceptance Criteria:**
- [ ] `golden_dataset.json` with 20+ cases (expanding to 50+ over time) covering: keyword, semantic, relational, temporal query categories
- [ ] `EvalHarness.__init__(self, pipeline, dataset_path)` — loads dataset
- [ ] `run_all() -> EvalReport` — executes all cases, computes metrics
- [ ] `EvalReport` dataclass: `timestamp`, `total_cases`, `passed`, `failed`, `metrics` (MRR, Precision, NDCG), `failed_cases`
- [ ] `EvalReport.save_snapshot(path)` — saves as versioned JSON
- [ ] `EvalReport.compare_to(previous)` — flags regressions > 0.05
- [ ] `just eval` command works

---

## Session 10: Heuristic Reranking & Quality Tuning

### Task 10.1 — Heuristic Reranker
**Status:** `done`
**File:** `src/cortex/query/reranker.py`
**Depends on:** Task 6.3, 8.1

**Description:** Heuristic-based reranking using recency, note type, link density, and status.

**Acceptance Criteria:**
- [ ] `HeuristicReranker.rerank(results: list[RankedResult], query: str, graph: GraphManager) -> list[RankedResult]`
- [ ] Boost factors: recency (newer = higher), note type priority (permanent > concept > source > inbox), inbound link count from graph, active status
- [ ] Configurable weights via `settings.yaml`
- [ ] Result `explanation` updated with reranking info (score change, which boosts applied)
- [ ] `tests/test_query/test_reranker.py` with 5+ tests: recency boost, type boost, link density boost, status penalty

---

### Task 10.2 — Pipeline Integration & Eval Run
**Status:** `done`
**File:** `src/cortex/query/pipeline.py` (extend)
**Depends on:** Task 10.1, 9.2

**Description:** Integrate reranker into pipeline and run the first eval comparison.

**Acceptance Criteria:**
- [ ] `QueryPipeline.execute()` now calls `HeuristicReranker.rerank()` after fusion
- [ ] Eval run produces snapshot v1
- [ ] No metric regresses by > 0.05 compared to v0
- [ ] `tests/test_query/test_pipeline.py` updated

---

## Session 11: Note Lifecycle Management

### Task 11.1 — LifecycleManager: Edit Flow
**Status:** `done`
**File:** `src/cortex/lifecycle/manager.py`
**Depends on:** Task 3.1, 3.2, 4.2, 5.4

**Description:** Implement the edit-with-review flow.

**Acceptance Criteria:**
- [ ] `LifecycleManager.__init__(self, vault, index, graph, draft_mgr)`
- [ ] `start_edit(self, note_id: str, changes: dict) -> NoteDraft` — loads note, applies changes to create a draft with diff
- [ ] `commit_edit(self, draft_id: str) -> Note` — approves draft, re-indexes in all stores
- [ ] Diff is included in the draft preview (shows what changed)
- [ ] `modified` timestamp is updated on commit
- [ ] `tests/test_lifecycle/test_edit.py` with 5+ tests: start edit, commit edit, verify re-index, verify diff in preview

---

### Task 11.2 — LifecycleManager: Archive & Supersede
**Status:** `done`
**File:** `src/cortex/lifecycle/manager.py` (extend)
**Depends on:** Task 11.1, 8.1

**Description:** Implement archival and supersession flows.

**Acceptance Criteria:**
- [ ] `archive_note(self, note_id: str) -> Note` — sets status=archived, archived_date, re-indexes
- [ ] `unarchive_note(self, note_id: str) -> Note` — restores to active, clears archived_date
- [ ] `supersede_note(self, old_note_id: str, new_note_id: str) -> tuple[Note, Note]` — bidirectional frontmatter links, SUPERSEDES graph edge, re-index both
- [ ] Score multipliers applied in query pipeline: archived=0.3, superseded=0.2
- [ ] `tests/test_lifecycle/test_archive.py` with 4+ tests
- [ ] `tests/test_lifecycle/test_supersede.py` with 4+ tests

---

### Task 11.3 — Staleness Detection
**Status:** `pending`
**File:** `src/cortex/lifecycle/staleness.py`
**Depends on:** Task 11.2, 8.1

**Description:** Identify stale notes using type-aware thresholds.

**Acceptance Criteria:**
- [ ] `detect_stale_notes(vault, graph, config) -> list[StaleCandidate]`
- [ ] `StaleCandidate` dataclass: `note`, `staleness_score`, `reasons`, `suggested_action`
- [ ] Thresholds: inbox/task=30d, source=90d, concept/permanent=365d
- [ ] Notes marked `evergreen: true` are exempt
- [ ] Orphan detection: notes with no inbound LINKS_TO edges
- [ ] Sorted by staleness score (most stale first)
- [ ] `tests/test_lifecycle/test_staleness.py` with 5+ tests

---

### Task 11.4 — Lifecycle MCP Tools & Eval Cases
**Status:** `pending`
**File:** `src/cortex/mcp/server.py` (extend), `evals/golden_dataset.json` (extend)
**Depends on:** Task 11.1, 11.2, 11.3, 7.1

**Description:** Expose lifecycle operations as MCP tools and add lifecycle eval cases.

**Acceptance Criteria:**
- [ ] MCP tools: `edit_note`, `archive_note`, `unarchive_note`, `supersede_note`, `detect_stale`
- [ ] Add 10+ lifecycle-specific eval cases to golden dataset (supersession ranking, archival penalty, edit consistency)
- [ ] Eval run produces snapshot v2 — no regression from v1
- [ ] Supersession correctness = 100%, edit consistency = 100%

---

## Session 12: Workflows

### Task 12.1 — Inbox Processing Workflow
**Status:** `pending`
**File:** `src/cortex/workflow/inbox.py`
**Depends on:** Task 2.3, 6.3

**Description:** Process inbox items — list them and suggest categorization.

**Acceptance Criteria:**
- [ ] `process_inbox(vault: VaultManager) -> list[InboxItem]` — lists all notes in `00-inbox/`
- [ ] `InboxItem` includes: note summary, suggested target folder, suggested tags, age in days
- [ ] MCP tool: `process_inbox` returns formatted inbox items for Claude to present
- [ ] `tests/test_workflow/test_inbox.py` with 3+ tests

---

### Task 12.2 — Review Generation Workflow
**Status:** `pending`
**File:** `src/cortex/workflow/review.py`
**Depends on:** Task 2.3, 6.3

**Description:** Generate weekly/monthly review summaries.

**Acceptance Criteria:**
- [ ] `generate_review(vault, period: str = "weekly", date: date = None) -> ReviewDraft` — aggregates notes from the period
- [ ] `ReviewDraft` includes: note counts by type, new captures, completed tasks, active projects, key themes
- [ ] MCP tool: `generate_review` returns the review data for Claude to format
- [ ] `tests/test_workflow/test_review.py` with 3+ tests

---

### Task 12.3 — Source Summarization & Staleness Review
**Status:** `pending`
**Files:** `src/cortex/workflow/summarize.py`, `src/cortex/workflow/staleness_review.py`
**Depends on:** Task 2.3, 11.3

**Description:** Source note summarization and guided staleness triage.

**Acceptance Criteria:**
- [ ] `summarize_source(note: Note) -> dict` — extracts key sections, metadata, and structure from a source note for Claude to summarize
- [ ] `staleness_review(vault, graph, config) -> list[StaleCandidate]` — runs staleness detection, formats candidates with suggested actions
- [ ] MCP tools: `summarize_source`, `staleness_review`
- [ ] `tests/test_workflow/test_summarize.py` with 2+ tests
- [ ] `tests/test_workflow/test_staleness_review.py` with 2+ tests

---

## Session 13: File Watching & Incremental Updates

### Task 13.1 — File Watcher
**Status:** `pending`
**File:** `src/cortex/vault/watcher.py`
**Depends on:** Task 2.3, 4.2, 5.4, 8.1

**Description:** Watchdog-based file watcher that triggers index updates on vault changes.

**Acceptance Criteria:**
- [ ] `VaultWatcher.__init__(self, vault_path, index_manager, graph_manager)`
- [ ] Detects file create, modify, delete events for `.md` files in vault
- [ ] Debouncing: waits 500ms after last event before processing (handles rapid saves)
- [ ] Ignores Obsidian temp files (`.md~`, `.obsidian/`)
- [ ] On create/modify: re-parses the file, calls `index_manager.reindex_note()` and `graph_manager.update_note()`
- [ ] On delete: calls `index_manager.remove_note()` and `graph_manager.remove_note()`
- [ ] `tests/test_vault/test_watcher.py` with 5+ tests: create event, modify event, delete event, debounce, ignore temp files

---

### Task 13.2 — Incremental Index Updates & Draft Conflict Resolution
**Status:** `pending`
**Files:** `src/cortex/index/manager.py` (extend), `src/cortex/capture/draft.py` (extend)
**Depends on:** Task 13.1, 3.1

**Description:** Handle edge cases for incremental updates and draft conflicts.

**Acceptance Criteria:**
- [ ] `IndexManager` handles re-index gracefully when note content hasn't actually changed (no-op optimization)
- [ ] Draft conflict: if a note has a pending draft but the vault file was modified externally, the draft is discarded (compare `modified` timestamps)
- [ ] `DraftManager.check_draft_freshness(draft_id: str, vault: VaultManager) -> bool` — returns False if underlying note was modified since draft creation
- [ ] `tests/test_capture/test_draft_conflict.py` with 3+ tests

---

## Session 14: Polish, Documentation & Docker Hardening

### Task 14.1 — Health Check & Error Handling
**Status:** `pending`
**Files:** `src/cortex/health.py`, error handling audit across all modules
**Depends on:** All previous tasks

**Description:** Add health check function for Docker and audit error handling.

**Acceptance Criteria:**
- [ ] `health_check() -> dict` — returns status of: Python process, DuckDB accessibility, vault path readability, embedding model loaded
- [ ] All MCP tools have try/except with clear error messages (not raw stack traces)
- [ ] Missing vault path → clear error suggesting volume mount check
- [ ] Missing index → clear error suggesting `rebuild_index`

---

### Task 14.2 — Final Eval & Documentation
**Status:** `pending`
**Files:** `README.md` updates, eval final run
**Depends on:** Task 14.1

**Description:** Run final eval, verify all success metrics, update documentation.

**Acceptance Criteria:**
- [ ] Final eval snapshot (`v_final`) meets all targets: MRR@10 ≥ 0.7, Precision@5 ≥ 0.6, NDCG@10 ≥ 0.65
- [ ] Supersession correctness = 100%, edit consistency = 100%
- [ ] `README.md` has quick-start for both Docker and bare-metal paths
- [ ] Claude Code MCP config snippet documented
- [ ] `docker compose up` → configure Claude Code → working system within 10 minutes

---

*End of Task Plan — 35 atomic tasks across 14 sessions*
