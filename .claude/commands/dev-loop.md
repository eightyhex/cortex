---
description: Run the task-driven development loop to implement pending tasks
---

This project uses an atomic task system for development. Tasks are defined in `.cortex-tasks/TASKS.md` and progress is tracked in `.cortex-tasks/PROGRESS.md`.

## Default behavior: Launch the dev loop as a background process

Run `./scripts/dev-loop.sh` in the background using the Bash tool with `run_in_background: true`. This spawns separate Claude Code sessions (via `claude -p`) that work through pending tasks autonomously.

1. First, check how many pending tasks remain by counting `**Status:** \`pending\`` lines in `.cortex-tasks/TASKS.md`
2. Launch the script in the background:
   - If the user specified a number of tasks: `./scripts/dev-loop.sh --max N`
   - Otherwise: `./scripts/dev-loop.sh`
3. Tell the user the loop is running and how many tasks are queued
4. When notified that the background process completed, read `.cortex-tasks/PROGRESS.md` and report:
   - Which tasks were completed
   - Any failures or blockers logged
   - What the next pending task is (if any)

## If the user says "interactive" or "here": Run the next task in this session

Follow the workflow defined in `CLAUDE.md`:

1. Read `.cortex-tasks/PROGRESS.md` to find the next pending task
2. Read that task in `.cortex-tasks/TASKS.md` for full acceptance criteria
3. Read relevant source files and `docs/02-ARCHITECTURE.md` sections
4. Implement the task — write code and tests
5. Run tests with `uv run pytest` (or the specific test file)
6. Update `.cortex-tasks/PROGRESS.md`: set last completed task, next task, add log entry
7. Update `.cortex-tasks/TASKS.md`: change the task status from `pending` to `done`
8. Commit with message: `task X.Y: <short description>`

## Rules

- One task per session unless trivially small
- Always run tests before marking done
- Never skip acceptance criteria
- If blocked, document in PROGRESS.md and move to next unblocked task

$ARGUMENTS
