# Cortex — Development Progress

> This file is the handoff document between agent sessions. Each agent reads this to know what's done and what's next.

## Current State

**Last updated:** 2026-03-15
**Last completed task:** Task 1.4 — Dockerfile & Docker Compose
**Next task:** Task 1.5 — Justfile Dev Commands
**Session:** 1 of 14

## Completed Tasks

- Task 1.1 — Pydantic Config Module ✅
- Task 1.2 — Vault Directory Scaffolding ✅
- Task 1.3 — Note Templates Module ✅
- Task 1.4 — Dockerfile & Docker Compose ✅

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

<!-- Example entry:
### 2026-03-15 — Task 1.1 ✅
- Implemented CortexConfig in src/cortex/config.py
- Tests: tests/test_config.py (3 tests, all pass)
- Notes: Used PyYAML for settings loading instead of built-in, added to dependencies
- Duration: ~15 min
-->
