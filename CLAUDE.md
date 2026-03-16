# Cortex — Agent Development Instructions

## Project Overview

Cortex is a local-first, AI-native second brain. See `docs/` for full specs:
- `docs/01-PRODUCT_REQUIREMENTS.md` — PRD
- `docs/02-ARCHITECTURE.md` — Technical Design
- `docs/03-CRITICAL_DECISIONS.md` — Decision rationale

## Task-Driven Development

This project uses an atomic task system for multi-session development.

### Key Files
- `.cortex-tasks/TASKS.md` — All tasks with acceptance criteria (read-only reference)
- `.cortex-tasks/PROGRESS.md` — Progress tracker and handoff log (update after each task)

### Agent Workflow (per session)

1. **Read** `.cortex-tasks/PROGRESS.md` to find the next pending task
2. **Read** the task in `.cortex-tasks/TASKS.md` for full acceptance criteria
3. **Read** relevant sections of `docs/02-ARCHITECTURE.md` for implementation details
4. **Implement** the task — write code and tests
5. **Run tests** with `uv run pytest` (or the specific test file)
6. **Update** `.cortex-tasks/PROGRESS.md`:
   - Set "Last updated" to today's date
   - Set "Last completed task" to the task you just finished
   - Set "Next task" to the next pending task
   - Add a log entry with: what you did, which files you changed, test results, any notes
7. **Update** `.cortex-tasks/TASKS.md`: change the task status from `pending` to `done`
8. **Commit** with message: `task X.Y: <short description>`

### Rules
- Complete **one task per session** (unless it's trivially small)
- Always run tests before marking a task done
- If blocked, document the blocker in PROGRESS.md and move to the next unblocked task
- Never skip acceptance criteria — each checkbox must be satisfied
- Keep implementation minimal — match the TDD spec, don't over-engineer

## Code Style
- Python 3.14+, type hints on public APIs
- Tests in `tests/` mirroring `src/` structure
- Use `uv run pytest` to run tests
- Follow existing patterns in the codebase

## Architecture Quick Reference
- MCP server: FastMCP 3.x, stdio transport
- Storage: Obsidian vault (source of truth) + DuckDB (FTS) + LanceDB (vectors) + NetworkX (graph)
- All derived data is rebuildable from vault
- Config: Pydantic Settings loading `settings.yaml`
