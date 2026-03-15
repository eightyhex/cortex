# Cortex — Development Progress

> This file is the handoff document between agent sessions. Each agent reads this to know what's done and what's next.

## Current State

**Last updated:** 2026-03-15
**Last completed task:** Task 3.1 — NoteDraft & DraftManager
**Next task:** Task 3.2 — VaultManager Write Operations
**Session:** 4 of 14

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

<!-- Example entry:
### 2026-03-15 — Task 1.1 ✅
- Implemented CortexConfig in src/cortex/config.py
- Tests: tests/test_config.py (3 tests, all pass)
- Notes: Used PyYAML for settings loading instead of built-in, added to dependencies
- Duration: ~15 min
-->
