# Cortex — Development Progress

> This file is the handoff document between agent sessions. Each agent reads this to know what's done and what's next.

## Current State

**Last updated:** 2026-03-15
**Last completed task:** Task 16.1 — Increase Snippet Length for Semantic Search Results
**Next task:** Task 16.2 — Increase Snippet Length for Lexical Search Results
**Session:** 20

## Completed Tasks

- Task 1.1 — Pydantic Config Module ✅
- Task 1.2 — Vault Directory Scaffolding ✅
- Task 1.3 — Note Templates Module ✅
- Task 1.4 — Dockerfile & Docker Compose ✅
- Task 1.5 — Justfile Dev Commands ✅
- Task 2.1 — Frontmatter Parser ✅
- Task 2.2 — Link & Tag Extractor ✅
- Task 2.3 — VaultManager Read Operations ✅
- Task 3.1 — NoteDraft & DraftManager ✅
- Task 3.2 — VaultManager Write Operations ✅
- Task 3.3 — Capture Commands ✅
- Task 3.4 — DraftManager.approve_draft Integration ✅
- Task 4.1 — LexicalIndex Core ✅
- Task 4.2 — IndexManager Skeleton ✅
- Task 5.1 — Embedding Model Wrapper ✅
- Task 5.2 — Semantic Boundary Chunker ✅
- Task 5.3 — SemanticIndex (LanceDB) ✅
- Task 5.4 — IndexManager Integration with SemanticIndex ✅
- Task 6.1 — Reciprocal Rank Fusion ✅
- Task 6.2 — Context Assembler ✅
- Task 6.3 — QueryPipeline ✅
- Task 7.1 — MCP Server Setup & Capture Tools ✅
- Task 7.2 — MCP Search & Admin Tools ✅
- Task 8.1 — GraphManager & Graph Builder ✅
- Task 8.2 — Graph Queries ✅
- Task 8.3 — Graph Integration into QueryPipeline ✅
- Task 9.1 — Eval Metrics ✅
- Task 9.2 — Golden Dataset & Eval Harness ✅
- Task 10.1 — Heuristic Reranker ✅
- Task 10.2 — Pipeline Integration & Eval Run ✅
- Task 11.1 — LifecycleManager: Edit Flow ✅
- Task 11.2 — LifecycleManager: Archive & Supersede ✅
- Task 11.3 — Staleness Detection ✅
- Task 11.4 — Lifecycle MCP Tools & Eval Cases ✅
- Task 12.1 — Inbox Processing Workflow ✅
- Task 12.2 — Review Generation Workflow ✅
- Task 12.3 — Source Summarization & Staleness Review ✅
- Task 13.1 — File Watcher ✅
- Task 13.2 — Incremental Index Updates & Draft Conflict Resolution ✅
- Task 14.1 — Health Check & Error Handling ✅
- Task 14.2 — Final Eval & Documentation ✅
- Task 15.1 — Wire Graph Manager into search_vault MCP Tool ✅
- Task 15.2 — Wire RerankerConfig from Settings into QueryPipeline ✅
- Task 15.3 — Add path Field to Semantic Index Schema ✅
- Task 15.4 — Add status, modified, and supersession Fields to Semantic Index ✅
- Task 15.5 — Populate Snippets for Graph Search Results ✅
- Task 15.6 — Ensure Reranker Handles Notes from All Search Sources ✅
- Task 15.7 — Integration Test: Full Search Pipeline with All Components Wired ✅
- Task 16.1 — Increase Snippet Length for Semantic Search Results ✅

## Notes & Decisions

- Record any implementation decisions, blockers, or deviations from the task plan here.
- Each agent should append to this section, not overwrite.

---

## Log

(Each agent appends an entry here when it completes a task)

### 2026-03-15 — Task 1.1 ✅
- Implemented CortexConfig with nested Pydantic models for vault, index, embeddings, search, lifecycle, draft, and mcp sections
- YAML loading with settings.yaml → settings.example.yaml fallback via custom pydantic-settings source
- Environment variable overrides work with CORTEX_ prefix and __ nested delimiter
- Files: `src/cortex/config.py`, `tests/test_config.py`
- Tests: 6 tests, all pass (default loading, YAML loading, example fallback, env override, missing file defaults, Path type check)

### 2026-03-15 — Task 1.2 ✅
- Implemented `scaffold_vault(vault_path)` in `src/cortex/vault/manager.py`
- Creates all 9 folders, copies template files from `vault.example/_templates/`, idempotent
- Files: `src/cortex/vault/manager.py`, `tests/test_vault/test_scaffold.py`
- Tests: 4 tests, all pass (folder creation, idempotent re-scaffold, template copy, no-overwrite)

### 2026-03-15 — Task 1.3 ✅
- Implemented `render_template()` in `src/cortex/vault/templates.py`
- Supports all 8 note types: inbox, daily, task, source, concept, permanent, project, review
- Frontmatter includes: id (UUID), title, type, created, modified, tags, status
- Task type adds due_date and priority; source type adds source_url
- Output is valid Obsidian-compatible markdown (YAML frontmatter between `---` delimiters)
- Files: `src/cortex/vault/templates.py`, `tests/test_vault/test_templates.py`
- Tests: 12 tests, all pass (one per note type, defaults, invalid type, comprehensive coverage)

### 2026-03-15 — Task 1.4 ✅
- Multi-stage Dockerfile: deps → model download → runtime (3 stages for lean image + fast rebuilds)
- docker-compose.yml with vault bind mount (CORTEX_VAULT_PATH env var, default ./vault), named cortex-data volume, stdin_open, healthcheck
- docker-compose.gpu.yml override with NVIDIA GPU support for accelerated embedding
- Updated scripts/docker-entrypoint.sh: scaffolds vault if empty (using scaffold_vault), creates data dir, warms embedding model, exec "$@"
- Updated .dockerignore: removed uv.lock exclusion (needed for --frozen install), kept all other exclusions
- Files: `Dockerfile`, `docker-compose.yml`, `docker-compose.gpu.yml`, `scripts/docker-entrypoint.sh`, `.dockerignore`
- Tests: 22 existing tests still pass (no new tests needed — Docker files are config, not code)

### 2026-03-15 — Task 1.5 ✅
- Updated justfile with all required dev and Docker commands
- Commands: `dev`, `test`, `lint`, `format`, `fmt` (alias), `index-rebuild`, `eval`, `docker-build`, `docker-up`, `docker-down`, `docker-shell`
- `just dev` runs `uv run python -m cortex.main`; `just test` runs `uv run pytest`; `just docker-build` runs `docker compose build`
- Added `docker-shell` for interactive container access
- Files: `justfile`
- Tests: 22 existing tests still pass (justfile is config, not code)

### 2026-03-15 — Task 2.1 ✅
- Implemented `Note` dataclass and `parse_note()` in `src/cortex/vault/parser.py`
- Uses `python-frontmatter` to extract YAML frontmatter from markdown files
- Handles missing frontmatter, missing fields, empty files gracefully with sensible defaults
- Note dataclass includes all fields: id, title, note_type, path, content, frontmatter, created, modified, tags, links, status, supersedes, superseded_by, archived_date
- Files: `src/cortex/vault/parser.py`, `tests/test_vault/test_parser.py`
- Tests: 9 tests, all pass (valid note, missing frontmatter, missing fields, empty file, all note types, unicode content, task fields, source fields, supersession fields)

### 2026-03-15 — Task 2.2 ✅
- Implemented `extract_wikilinks()`, `extract_markdown_links()`, `extract_inline_tags()` in `src/cortex/vault/parser.py`
- Added `Link` dataclass with `source_id`, `target_id`, `target_title`, `link_type`
- `parse_note()` now populates `note.links` with extracted wikilinks as `Link` objects
- `parse_note()` merges inline tags with frontmatter tags (deduplicated, order preserved)
- Inline tag extraction excludes tags inside code blocks (fenced and inline)
- Files: `src/cortex/vault/parser.py`, `tests/test_vault/test_links.py`
- Tests: 16 new tests, 47 total — all pass (wikilinks, aliased wikilinks, markdown links, inline tags, code block exclusion, mixed content, tag merging, no links)

### 2026-03-15 — Task 2.3 ✅
- Implemented `VaultManager` class in `src/cortex/vault/manager.py` with read operations
- `__init__(vault_path, config)` — stores resolved path, verifies vault exists
- `get_note(note_id)` — finds note by UUID scanning all vault notes
- `get_note_by_path(path)` — parses note at given path (absolute or relative)
- `list_notes(folder, note_type)` — lists all notes with optional filtering
- `scan_vault()` — parses all `.md` files excluding `_templates/`
- Files: `src/cortex/vault/manager.py`, `tests/test_vault/test_manager.py`
- Tests: 14 new tests, 61 total — all pass (init, missing path, scan, template exclusion, get by id, get by path, list with filters, empty results)

### 2026-03-15 — Task 3.1 ✅
- Implemented `NoteDraft` dataclass with `render_preview()`, `render_markdown()`, and `apply_edits()` methods
- Implemented `DraftManager` with `create_draft()`, `get_draft()`, `update_draft()`, `reject_draft()`, and `_cleanup_stale_drafts()`
- File-based JSON persistence in `data/drafts/{draft_id}.json`
- File naming: `{date}-{type}-{short-hash}-{slug}.md` with slugified titles
- Note type to folder mapping for all 8 note types
- Stale draft cleanup (>24h) runs on DraftManager init
- Files: `src/cortex/capture/draft.py`, `tests/test_capture/test_draft.py`
- Tests: 20 new tests, 81 total — all pass (preview, markdown render, edits, JSON round-trip, cleanup, reject, folder mapping, file naming)

### 2026-03-15 — Task 3.2 ✅
- Implemented `create_note(draft)` and `update_note(note_id, content, metadata)` in `VaultManager`
- `create_note` writes rendered markdown to `{vault_path}/{target_folder}/{target_filename}`, ensures parent dir exists
- `update_note` finds note by ID, merges metadata, bumps `modified` timestamp, rewrites file
- Files: `src/cortex/vault/manager.py`, `tests/test_vault/test_manager_write.py`
- Tests: 7 new tests, 88 total — all pass (create from draft, ensure parent dir, file content match, update content, update metadata, bump modified, persist to disk)

### 2026-03-15 — Task 3.3 ✅
- Implemented four capture commands: `capture_thought`, `add_task`, `save_link`, `create_note`
- Each function takes a `DraftManager` and produces a `NoteDraft` via `create_draft()`
- `capture_thought` auto-derives title from first line (truncated to 60 chars)
- `save_link` defaults title to URL when not provided
- `create_note` is generic and works with any note type (concept, permanent, project, etc.)
- Files: `src/cortex/capture/thought.py`, `task.py`, `link.py`, `note.py`, `tests/test_capture/test_commands.py`
- Tests: 16 new tests, 104 total — all pass

### 2026-03-15 — Task 3.4 ✅
- Implemented `DraftManager.approve_draft(draft_id, vault)` in `src/cortex/capture/draft.py`
- Calls `vault.create_note(draft)` to write the .md file, then deletes the draft JSON
- Files: `src/cortex/capture/draft.py`, `tests/test_capture/test_approve.py`
- Tests: 4 new tests, 108 total — all pass (approve creates file, approve deletes draft, approve returns valid Note, nonexistent draft raises)

### 2026-03-15 — Task 4.2 ✅
- Implemented `IndexManager` class in `src/cortex/index/manager.py`
- `__init__(config)` — initializes LexicalIndex with db_path derived from config
- `index_note(note)` — delegates to lexical index
- `remove_note(note_id)` — delegates to lexical index
- `reindex_note(note)` — remove + re-add
- `rebuild_all(notes)` — full rebuild delegation
- Files: `src/cortex/index/manager.py`, `tests/test_index/test_manager.py`
- Tests: 4 new tests, 129 total — all pass (index+search, remove, reindex, rebuild_all)

### 2026-03-15 — Task 5.1 ✅
- Implemented `EmbeddingModel` wrapper in `src/cortex/index/models.py`
- `__init__(model_name)` with default `nomic-ai/nomic-embed-text-v1.5`, lazy loading (model loaded on first use)
- `embed(text)` returns 768-dim `list[float]`, `embed_batch(texts)` for batch embedding
- `tokenize_count(text)` uses model's tokenizer to count tokens
- Added `einops` dependency required by nomic model
- Files: `src/cortex/index/models.py`, `tests/test_index/test_models.py`
- Tests: 7 new tests, 136 total — all pass (lazy loading, single embed, batch embed, empty batch, dimension check, tokenize count, different texts produce different vectors)

### 2026-03-15 — Task 4.1 ✅
- Implemented `LexicalIndex` class in `src/cortex/index/lexical.py` with DuckDB-backed full-text search
- `__init__(db_path)` — creates/opens DuckDB database, creates `notes` table if not exists
- `index_note(note)` — upserts note (DELETE + INSERT) and rebuilds FTS index
- `remove_note(note_id)` — deletes note from table
- `rebuild(notes)` — drops and recreates table + FTS index, inserts all notes
- `search(query, limit, filters)` — BM25 full-text search with optional filters (note_type, tags, status, date_range)
- `SearchResult` dataclass with: note_id, title, score, snippet, note_type, path
- Tags stored as both `VARCHAR[]` (filtering) and `tags_text VARCHAR` (FTS)
- Files: `src/cortex/index/lexical.py`, `tests/test_index/test_lexical.py`
- Tests: 17 new tests, 125 total — all pass (index, upsert, remove, rebuild, search by keyword, filters, BM25 ranking, limit, snippets, empty results)

### 2026-03-15 — Task 5.2 ✅
- Implemented `chunk_note()` and `Chunk` dataclass in `src/cortex/index/chunker.py`
- Splits on paragraph boundaries (`\n\n`) first, then sentence boundaries for oversized paragraphs
- Merges small consecutive paragraphs up to target_tokens
- Short notes (< target_tokens) become a single chunk
- Chunk ID format: `{note_id}__chunk_{N}`
- Files: `src/cortex/index/chunker.py`, `tests/test_index/test_chunker.py`
- Tests: 8 new tests, 144 total — all pass (short note, long note, paragraph split, sentence split, token counting, chunk ID format, empty content, merging small paragraphs)

### 2026-03-15 — Task 5.3 ✅
- Implemented `SemanticIndex` class in `src/cortex/index/semantic.py` backed by LanceDB
- `__init__(db_path, model)` — creates/opens LanceDB, creates `chunks` table with PyArrow schema
- `index_note(note)` — chunks via `chunk_note()`, embeds via `EmbeddingModel.embed_batch()`, stores in LanceDB
- `remove_note(note_id)` — deletes all chunks for a note
- `rebuild(notes)` — drops and recreates table, re-indexes all notes
- `search(query, limit)` — embeds query, cosine similarity search, deduplicates by note_id (keeps highest-scoring chunk)
- LanceDB schema: id, note_id, title, note_type, text, vector (768-dim float32), tags, created
- Files: `src/cortex/index/semantic.py`, `tests/test_index/test_semantic.py`
- Tests: 7 new tests, 151 total — all pass (index+search, empty index, remove, rebuild, semantic relevance, upsert on reindex, result fields)

### 2026-03-15 — Task 5.4 ✅
- Wired `SemanticIndex` into `IndexManager` so both lexical and semantic indexes are updated together
- `IndexManager.__init__` now initializes both `LexicalIndex` and `SemanticIndex` (with `EmbeddingModel`)
- All methods (`index_note`, `remove_note`, `reindex_note`, `rebuild_all`) delegate to both indexes
- Added `semantic` property to expose the `SemanticIndex` instance
- Files: `src/cortex/index/manager.py`, `tests/test_index/test_manager.py`
- Tests: 6 tests (up from 4), 153 total — all pass (lexical search, semantic search, remove from both, reindex both, rebuild both, semantic property exposed)

### 2026-03-15 — Task 6.1 ✅
- Implemented `reciprocal_rank_fusion()` in `src/cortex/query/fusion.py`
- `FusedResult` dataclass extends SearchResult with `matched_by` field tracking contributing systems
- RRF formula: `score(d) = sum(1 / (k + rank_i(d)))` with configurable k (default 60)
- Deduplicates by note_id, combines scores, preserves metadata from first occurrence
- Optional `labels` parameter names each result list for explainability
- Files: `src/cortex/query/fusion.py`, `tests/test_query/test_fusion.py`
- Tests: 8 new tests, all pass (merge two lists, merge three lists, deduplication, empty handling, score ordering, matched_by tracking, labels mismatch, metadata preservation)

### 2026-03-15 — Task 6.2 ✅
- Implemented `ContextAssembler` class in `src/cortex/query/context.py`
- `assemble(results, query, max_tokens, notes)` formats fused results into structured context for Claude
- Output format: header (query + result count + retrieval methods), then per-result blocks (title, score, source, excerpt, tags, links, created)
- Truncates excerpts to fit within `max_tokens` budget using ~4 chars/token estimate
- Annotates superseded notes with `⚠ This note was superseded by: [title] (id: xxx)` warning
- Accepts optional `notes: dict[str, Note]` for metadata lookup (tags, links, created, supersession)
- Files: `src/cortex/query/context.py`, `tests/test_query/test_context.py`
- Tests: 6 new tests, 167 total — all pass (basic assembly, empty results, truncation, superseded annotation, no-notes fallback, budget exhaustion)

### 2026-03-15 — Task 6.3 ✅
- Implemented `QueryPipeline` class in `src/cortex/query/pipeline.py`
- `async execute(query, limit)` runs lexical and semantic search in parallel via asyncio, fuses via RRF, assembles context
- `QueryResult` dataclass: `query`, `results: list[RankedResult]`, `context: str`, `explanation: str`
- `RankedResult` dataclass: `note_id`, `title`, `score`, `matched_by: list[str]`, `snippet`, `note_type`
- Status-based score multipliers applied after fusion: active=1.0, draft=0.8, archived=0.3, superseded=0.2
- Graceful error handling for empty indexes (no FTS index, empty vector store)
- Files: `src/cortex/query/pipeline.py`, `tests/test_query/test_pipeline.py`
- Tests: 6 new tests, 173 total — all pass (end-to-end query, status multipliers, explanation includes source systems, empty results, limit respected, ranked result fields)

### 2026-03-15 — Task 7.1 ✅
- Implemented `FastMCP` server in `src/cortex/mcp/server.py` with `init_server()` for dependency injection
- Capture tools: `mcp_capture_thought`, `mcp_add_task`, `mcp_save_link`, `mcp_create_note` — all return `{draft_id, preview, target_folder, target_filename}`
- Draft lifecycle tools: `approve_draft`, `update_draft`, `reject_draft`
- All capture tool descriptions instruct Claude to show preview and ask for approval before approving
- Entry point `src/cortex/main.py` — `uv run python -m cortex.main` starts the server via stdio transport
- Files: `src/cortex/mcp/server.py`, `src/cortex/main.py`, `tests/test_mcp/__init__.py`, `tests/test_mcp/test_server.py`
- Tests: 18 new tests, 191 total — all pass

### 2026-03-15 — Task 7.2 ✅
- Added 4 new MCP tools: `search_vault`, `get_note`, `rebuild_index`, `vault_stats`
- `search_vault` runs QueryPipeline (lexical+semantic), returns structured context with optional note_type filter
- `get_note` returns full note content/metadata by ID
- `rebuild_index` triggers full index rebuild from vault, tracks last rebuild timestamp
- `vault_stats` returns note counts by type, index sizes (lexical notes, semantic chunks), last rebuild time
- Extended `init_server` to accept optional `IndexManager` for search/admin tools
- Error handling: clear messages for missing index, vault not found, note not found
- Files: `src/cortex/mcp/server.py`, `tests/test_mcp/test_search_admin.py`
- Tests: 20 new tests, 211 total — all pass

### 2026-03-15 — Task 8.2 ✅
- Implemented graph query functions in `src/cortex/graph/queries.py`
- `get_neighbors(graph, note_id, depth)` — BFS neighbors via undirected view
- `find_path(graph, source_id, target_id)` — shortest path via undirected view
- `get_cluster(graph, note_id, max_nodes)` — ego graph with expanding radius
- `get_project_notes(graph, project_id)` — notes linked via BELONGS_TO_PROJECT edges
- `graph_search(graph, note_ids, depth)` — expands seed IDs, returns SearchResults with score decay by hop distance, skips project nodes
- Files: `src/cortex/graph/queries.py`, `tests/test_graph/test_queries.py`
- Tests: 18 new tests, 241 total — all pass

### 2026-03-15 — Task 8.3 ✅
- Wired `GraphManager` into `QueryPipeline` as optional third search source
- `execute()` collects top-N note IDs from lexical+semantic as seeds, calls `graph_search()` with depth=1
- Graph results included in RRF fusion alongside lexical and semantic
- `explanation` field includes "graph" when graph contributes results
- Added `_safe_graph_search()` with graceful error handling
- Files: `src/cortex/query/pipeline.py`, `tests/test_query/test_pipeline.py`
- Tests: 1 new test (graph_integration), 242 total — all pass

### 2026-03-15 — Task 8.1 ✅
- Implemented `GraphManager` in `src/cortex/graph/manager.py` and graph building helpers in `src/cortex/graph/builder.py`
- `GraphManager.__init__(graph_path)` loads from GraphML or creates empty `nx.MultiDiGraph`
- `save()` writes GraphML with `.bak` backup
- `build_from_vault(notes)` clears graph, adds note nodes + project nodes, LINKS_TO/BELONGS_TO_PROJECT/SUPERSEDES edges
- `update_note(note)` updates/adds a single node and re-creates its outgoing edges
- `remove_note(note_id)` removes node and all connected edges
- `builder.py` has `add_note_node()`, `add_edges_for_note()`, `build_graph()` — two-pass construction (nodes first, then edges)
- Node attributes: `node_type` (note/project), `title`, `note_type`, `path`
- Edge attributes: `rel_type` (LINKS_TO / BELONGS_TO_PROJECT / SUPERSEDES)
- Project nodes created from frontmatter `project` field with `project-{name}` ID format
- Files: `src/cortex/graph/manager.py`, `src/cortex/graph/builder.py`, `tests/test_graph/test_manager.py`
- Tests: 12 new tests, 223 total — all pass

### 2026-03-15 — Task 9.1 ✅
- Implemented `mrr_at_k()`, `precision_at_k()`, `ndcg_at_k()` in `evals/metrics.py`
- MRR: returns 1/rank of first relevant result in top-k
- Precision: fraction of top-k results that are relevant
- NDCG: normalized DCG with binary relevance
- All return 0.0 for empty/no-match cases
- Files: `evals/metrics.py`, `tests/test_evals/test_metrics.py`
- Tests: 18 new tests, all pass (perfect ranking, partial match, no match, beyond k, empty inputs, edge cases)

### 2026-03-15 — Task 9.2 ✅
- Implemented `EvalHarness` class with `run_all()` and `run_tagged()` methods
- Implemented `EvalReport` dataclass with `save_snapshot(path)` and `compare_to(previous)` for regression detection (> 0.05 threshold)
- `EvalReport.from_snapshot()` loads saved snapshots for comparison
- `CaseResult` tracks per-case MRR, Precision, NDCG and pass/fail
- `golden_dataset.json` with 25 cases covering keyword (8), semantic (8), relational (4), temporal (3), and mixed categories
- Snapshot versioning: auto-increments `snapshot_v000.json`, `snapshot_v001.json`, etc.
- `just eval` runs via `uv run python -m pytest evals/ -v`
- Files: `evals/harness.py`, `evals/golden_dataset.json`, `tests/test_evals/test_harness.py`
- Tests: 15 new tests, 275 total — all pass

### 2026-03-15 — Task 10.1 ✅
- Implemented `HeuristicReranker` class in `src/cortex/query/reranker.py`
- `rerank(results, query, graph)` applies four heuristic boost signals after fusion
- Recency boost: exponential decay with configurable half-life (default 90 days)
- Note type priority: permanent(1.0) > concept(0.8) > source(0.6) > project(0.5) > review(0.4) > task(0.3) > daily(0.2) > inbox(0.1)
- Inbound link density: normalized count from graph (higher = more authoritative)
- Status boost: active(1.0) > draft(0.5) > archived/superseded(0.0)
- Added `RerankerConfig` to `src/cortex/config.py` with configurable weights (recency, type, link, status) and halflife
- Added reranker section to `settings.example.yaml`
- Metadata fetched from DuckDB lexical index; link counts from NetworkX graph
- Files: `src/cortex/query/reranker.py`, `src/cortex/config.py`, `settings.example.yaml`, `tests/test_query/test_reranker.py`
- Tests: 8 new tests, 283 total — all pass (recency boost, type boost, link density boost, status penalty, empty results, configurable weights, scores always increase, no-graph fallback)

### 2026-03-15 — Task 10.2 ✅
- Integrated `HeuristicReranker` into `QueryPipeline.execute()` — called after RRF fusion, replacing manual status multipliers
- Reranker applies recency, note type, link density, and status boosts via configurable weights
- Lazy import used to break circular dependency between `pipeline.py` and `reranker.py`
- Removed `STATUS_MULTIPLIERS` constant and `_build_status_map()` method (reranker handles status natively)
- Added `reranker_config` parameter to `QueryPipeline.__init__` (defaults to `RerankerConfig()`)
- Added eval snapshot v0/v1 comparison test verifying no regression > 0.05
- Files: `src/cortex/query/pipeline.py`, `tests/test_query/test_pipeline.py`, `tests/test_evals/test_harness.py`
- Tests: 285 total — all pass (8 pipeline tests including 2 new reranker tests, 1 new eval snapshot test)

### 2026-03-15 — Task 11.1 ✅
- Implemented `LifecycleManager` class in `src/cortex/lifecycle/manager.py` with edit-with-review flow
- `__init__(vault, index, graph, draft_mgr)` — accepts all required dependencies
- `start_edit(note_id, changes)` — loads note, applies changes, generates unified diff, creates and persists a NoteDraft with `_edit_note_id` and `_diff` metadata
- `commit_edit(draft_id)` — approves edit draft, updates vault note (content + metadata), re-indexes in lexical+semantic indexes, updates graph, cleans up draft
- Diff included in draft preview via `_diff` frontmatter field
- `modified` timestamp updated on commit via `VaultManager.update_note()`
- Files: `src/cortex/lifecycle/manager.py`, `tests/test_lifecycle/__init__.py`, `tests/test_lifecycle/test_edit.py`
- Tests: 11 new tests, 296 total — all pass (start_edit creates draft, diff included, title preserved/changed, tags changed, draft persisted, commit updates vault, commit reindexes, commit updates modified, commit removes draft, non-edit draft raises)

### 2026-03-15 — Task 11.2 ✅
- Implemented `archive_note(note_id)` — sets status=archived, archived_date, re-indexes in lexical+semantic+graph
- Implemented `unarchive_note(note_id)` — restores to active, clears archived_date (uses None to avoid parser ISO format error)
- Implemented `supersede_note(old_note_id, new_note_id)` — bidirectional frontmatter links (superseded_by/supersedes), SUPERSEDES graph edge, status=superseded on old note, re-indexes both
- Score multipliers already handled by HeuristicReranker (Task 10.2): archived=0.0 status boost, superseded=0.0 status boost
- Files: `src/cortex/lifecycle/manager.py`, `tests/test_lifecycle/test_archive.py`, `tests/test_lifecycle/test_supersede.py`
- Tests: 14 new tests (8 archive/unarchive + 6 supersede), 310 total — all pass

### 2026-03-15 — Task 11.3 ✅
- Implemented `detect_stale_notes(vault, graph, config)` in `src/cortex/lifecycle/staleness.py`
- `StaleCandidate` dataclass with `note`, `staleness_score`, `reasons`, `suggested_action`
- Type-aware thresholds: inbox/task=30d, source=90d, concept/permanent=365d (from `LifecycleConfig.staleness_thresholds`)
- Notes with `evergreen: true` frontmatter are exempt
- Orphan detection: notes with no inbound LINKS_TO edges get +0.5 score penalty
- Archived/superseded notes are skipped
- Suggested actions: "archive" (score>2.0), "categorize" (inbox), "review" (default)
- Results sorted by staleness_score descending (most stale first)
- Files: `src/cortex/lifecycle/staleness.py`, `tests/test_lifecycle/test_staleness.py`
- Tests: 8 new tests, 318 total — all pass

### 2026-03-15 — Task 11.4 ✅
- Added 6 lifecycle MCP tools: `edit_note`, `approve_edit`, `archive_note`, `unarchive_note`, `supersede_note`, `detect_stale`
- Extended `init_server()` with optional `graph` parameter; auto-creates `LifecycleManager` when both index and graph are available
- Added `_get_lifecycle()` and `_get_graph()` helper functions with proper error handling
- Added 11 lifecycle-specific eval cases (q026–q036) covering supersession ranking, archival penalty, and edit consistency
- Files: `src/cortex/mcp/server.py`, `evals/golden_dataset.json`, `tests/test_mcp/test_lifecycle_tools.py`
- Tests: 17 new tests, 335 total — all pass

### 2026-03-15 — Task 12.1 ✅
- Implemented `process_inbox(vault)` in `src/cortex/workflow/inbox.py`
- `InboxItem` dataclass with: note_id, title, summary, suggested_type, suggested_folder, suggested_tags, age_days, path
- Content heuristics: URLs → source/10-sources, TODO/FIXME/checkboxes → task/02-tasks, default → concept/20-concepts
- Summary truncated to 200 chars; items sorted by age descending (oldest first)
- MCP tool: `mcp_process_inbox` in `src/cortex/mcp/server.py` returns formatted items for Claude to present
- Files: `src/cortex/workflow/inbox.py`, `src/cortex/mcp/server.py`, `tests/test_workflow/test_inbox.py`
- Tests: 10 new tests, 345 total — all pass (empty inbox, list notes, ignore non-inbox, summary, URL suggestion, TODO suggestion, age calculation, sort order, tag suggestions, MCP tool integration)

### 2026-03-15 — Task 12.2 ✅
- Implemented `generate_review(vault, period, target_date)` in `src/cortex/workflow/review.py`
- `ReviewDraft` dataclass with: period, start/end dates, total_notes, counts_by_type, new_captures, completed_tasks, active_projects, key_themes
- Weekly period = 7 days lookback, monthly = 30 days
- New captures: inbox/thought notes in period; completed tasks: task notes with status=done; active projects: all active project notes from full vault
- Key themes extracted from tag frequency across period notes
- MCP tool: `mcp_generate_review` in `src/cortex/mcp/server.py` with optional period and target_date params
- Files: `src/cortex/workflow/review.py`, `src/cortex/mcp/server.py`, `tests/test_workflow/test_review.py`
- Tests: 9 new tests, 354 total — all pass (empty vault, weekly period filter, monthly range, counts by type, new captures, completed tasks, active projects, key themes, MCP tool integration)

### 2026-03-15 — Task 12.3 ✅
- Implemented `summarize_source(note)` in `src/cortex/workflow/summarize.py`
- Extracts: headings, URLs, word count, content excerpt, source_url, tags, status
- Implemented `staleness_review(vault, graph, config)` in `src/cortex/workflow/staleness_review.py`
- Wraps `detect_stale_notes()` with workflow interface, returns sorted StaleCandidate list
- MCP tools: `mcp_summarize_source` (by note_id), `mcp_staleness_review` (full vault scan with path in output)
- Files: `src/cortex/workflow/summarize.py`, `src/cortex/workflow/staleness_review.py`, `src/cortex/mcp/server.py`, `tests/test_workflow/test_summarize.py`, `tests/test_workflow/test_staleness_review.py`
- Tests: 10 new tests, 364 total — all pass

### 2026-03-15 — Task 13.1 ✅
- Implemented `VaultWatcher` and `_VaultEventHandler` in `src/cortex/vault/watcher.py`
- Watchdog-based file system watcher with 500ms debouncing (threading.Timer)
- Detects create, modify, delete, move events for `.md` files
- Ignores: non-.md files, `.md~` temp files, `.obsidian/`, `_templates/` directories
- On create/modify: parses note, calls `index_manager.reindex_note()` and `graph_manager.update_note()`
- On delete: looks up note_id from graph nodes by path, calls `remove_note()` on both
- Debouncing: rapid saves to same file only trigger one reindex
- Files: `src/cortex/vault/watcher.py`, `tests/test_vault/test_watcher.py`
- Tests: 12 new tests, 376 total — all pass (create event, modify event, delete event, delete unknown, debounce rapid, debounce different files, ignore non-md, ignore temp, ignore .obsidian, ignore _templates, accept normal md, start/stop)

### 2026-03-15 — Task 13.2 ✅
- Implemented no-op optimization in `IndexManager.reindex_note` using SHA-256 content hashing
- Hash covers: content, title, status, tags, modified timestamp — skips reindex when unchanged
- Implemented `DraftManager.check_draft_freshness(draft_id, vault)` — returns False if underlying note was modified after draft creation
- Stale edit drafts are auto-discarded (draft file deleted) when freshness check fails
- Non-edit drafts (no `_edit_note_id`) are always considered fresh
- Deleted notes cause edit drafts to be marked stale
- Files: `src/cortex/index/manager.py`, `src/cortex/capture/draft.py`, `tests/test_capture/test_draft_conflict.py`
- Tests: 8 new tests (4 reindex no-op + 4 draft freshness), 384 total — all pass

### 2026-03-15 — Task 14.1 ✅
- Implemented `health_check(config)` in `src/cortex/health.py` — returns status of Python process, DuckDB accessibility, vault path readability, embedding model loaded
- Overall status: "healthy" (all ok), "degraded" (vault ok but other issues), "unhealthy" (vault missing)
- Added `mcp_health_check` MCP tool in `src/cortex/mcp/server.py`
- Wrapped all unprotected MCP tools (4 capture tools, 3 draft lifecycle tools) with try/except returning clear error dicts
- Improved error messages: missing vault suggests volume mount check, missing index suggests `rebuild_index`
- Files: `src/cortex/health.py`, `src/cortex/mcp/server.py`, `tests/test_health.py`
- Tests: 8 new tests, 392 total — all pass

### 2026-03-15 — Task 14.2 ✅
- Added `TestFinalEval` class with 3 tests: `test_final_eval_meets_targets`, `test_supersession_correctness_100_percent`, `test_edit_consistency_100_percent`
- Final eval snapshot verifies MRR@10 >= 0.7, Precision@5 >= 0.6, NDCG@10 >= 0.65 — all pass
- Supersession correctness = 100% (superseded notes never outrank replacements)
- Edit consistency = 100% (edited notes remain findable after edits)
- Updated README.md: added Claude Code MCP config snippets for both Docker and bare-metal (uv)
- Updated README.md quick-start with clearer Docker and bare-metal sections
- Files: `tests/test_evals/test_harness.py`, `README.md`
- Tests: 395 total — all pass (3 new final eval tests)

### 2026-03-15 — Task 15.1 ✅
- Wired `_get_graph()` into `search_vault` MCP tool, passing graph to `QueryPipeline(..., graph=graph)`
- Graph lookup wrapped in try/except so search still works when graph is unavailable
- Search results now include notes discovered via graph expansion (matched_by includes "graph")
- Files: `src/cortex/mcp/server.py`, `tests/test_mcp/test_search_admin.py`
- Tests: 2 new tests (graph expansion, graceful fallback without graph), 401 total — all pass

### 2026-03-15 — Task 15.2 ✅
- Wired `RerankerConfig` from `_config.reranker` into `QueryPipeline` in `search_vault` MCP tool
- Previously, `search_vault` created `QueryPipeline` without passing `reranker_config`, so user settings in `settings.yaml` were silently ignored
- Now `QueryPipeline` receives the active config's reranker weights (recency, type, link, status)
- Files: `src/cortex/mcp/server.py`, `tests/test_mcp/test_search_admin.py`
- Tests: 1 new test (custom reranker config), 402 total — all pass

### 2026-03-15 — Task 15.3 ✅
- Added `path` field (`pa.utf8()`) to LanceDB `_schema` in `src/cortex/index/semantic.py`
- `index_note()` now stores `str(note.path)` in the `path` field for each chunk
- `search()` now returns `SearchResult` with the actual `path` value populated (via `row.get("path", "")`)
- `rebuild()` includes path in stored records (inherits from `index_note`)
- Files: `src/cortex/index/semantic.py`, `tests/test_index/test_semantic.py`
- Tests: 1 new test (`test_search_result_includes_path`), 403 total — all pass

### 2026-03-15 — Task 15.4 ✅
- Added `status`, `modified`, `supersedes`, `superseded_by` fields to LanceDB `_schema` in `src/cortex/index/semantic.py`
- Extended `SearchResult` dataclass in `src/cortex/index/lexical.py` with 4 optional fields (defaults to empty string)
- `index_note()` populates new fields from `note.status`, `note.modified`, and `note.frontmatter`
- `search()` returns `SearchResult` with all new fields populated from LanceDB rows
- `rebuild()` inherits new fields via `index_note()`
- Files: `src/cortex/index/semantic.py`, `src/cortex/index/lexical.py`, `tests/test_index/test_semantic.py`
- Tests: 1 new test (`test_search_result_includes_status_and_metadata`), 404 total — all pass

### 2026-03-15 — Task 15.5 ✅
- Added optional `vault` parameter to `graph_search()` in `src/cortex/graph/queries.py`
- When vault is provided, fetches note content and populates `snippet` with first 200 characters
- When vault is not provided, falls back to `snippet=""` (no regression)
- Updated `QueryPipeline._safe_graph_search()` in `src/cortex/query/pipeline.py` to pass `self._vault` to `graph_search()`
- Files: `src/cortex/graph/queries.py`, `src/cortex/query/pipeline.py`, `tests/test_graph/test_queries.py`
- Tests: 2 new tests (vault populates snippets, without vault empty snippets), 406 total — all pass

### 2026-03-15 — Task 15.7 ✅
- Created `tests/test_mcp/test_search_integration.py` with 7 integration tests
- Full setup fixture: 6 notes (permanent, concept, source, archived, task, project) with wikilinks
- Builds all 3 indexes (lexical, semantic, graph) and initializes MCP server
- Verified: search results include created/modified ISO timestamps
- Verified: context output shows actual dates (not "unknown")
- Verified: graph-expanded results include non-empty snippets
- Verified: archived notes scored lower than active notes
- Verified: custom reranker config from settings is respected
- Verified: multiple search sources (lexical, semantic) contribute results
- Files: `tests/test_mcp/test_search_integration.py`
- Tests: 7 new tests, 415 total — all pass

### 2026-03-15 — Task 15.6 ✅
- Added optional `semantic: SemanticIndex` parameter to `HeuristicReranker.__init__`
- `_fetch_metadata()` now falls back to semantic index when lexical lookup misses notes
- New `_fetch_semantic_metadata()` queries LanceDB for note_type, status, created fields
- `QueryPipeline` now passes `semantic` to `HeuristicReranker` constructor
- If both lexical and semantic lookups fail, note gets default scoring (no crash)
- Files: `src/cortex/query/reranker.py`, `src/cortex/query/pipeline.py`, `tests/test_query/test_reranker.py`
- Tests: 2 new tests (semantic fallback, both-fail default scoring), 408 total — all pass

### 2026-03-15 — Task 16.1 ✅
- Removed `[:200]` truncation from `SemanticIndex.search()` snippet at `semantic.py:163`
- Semantic search now returns the full chunk text in `SearchResult.snippet`
- New test: `test_semantic_snippet_returns_full_chunk_text` verifies snippet > 200 chars and matches full content
- Files: `src/cortex/index/semantic.py`, `tests/test_index/test_semantic.py`
- Tests: 10 semantic tests, all pass

<!-- Example entry:
### 2026-03-15 — Task 1.1 ✅
- Implemented CortexConfig in src/cortex/config.py
- Tests: tests/test_config.py (3 tests, all pass)
- Notes: Used PyYAML for settings loading instead of built-in, added to dependencies
- Duration: ~15 min
-->
