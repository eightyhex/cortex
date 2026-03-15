# Cortex — Development Progress

> This file is the handoff document between agent sessions. Each agent reads this to know what's done and what's next.

## Current State

**Last updated:** 2026-03-15
**Last completed task:** Task 8.2 — Graph Queries
**Next task:** Task 8.3 — Graph Integration into QueryPipeline
**Session:** 18 of 14

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

<!-- Example entry:
### 2026-03-15 — Task 1.1 ✅
- Implemented CortexConfig in src/cortex/config.py
- Tests: tests/test_config.py (3 tests, all pass)
- Notes: Used PyYAML for settings loading instead of built-in, added to dependencies
- Duration: ~15 min
-->
