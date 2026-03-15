#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Cortex Dev Loop — Runs Claude Code agents in a loop, one task at a time.
#
# Usage:
#   ./scripts/dev-loop.sh              # Run until interrupted (Ctrl+C)
#   ./scripts/dev-loop.sh --max 5      # Run at most 5 iterations
#   ./scripts/dev-loop.sh --dry-run    # Show what would be done, don't run
#
# What it does:
#   1. Launches Claude Code with a prompt to pick up the next task
#   2. Claude reads PROGRESS.md, implements the task, updates progress
#   3. Claude commits the work
#   4. Script waits, then starts a new session for the next task
#
# To stop: Ctrl+C (the current task will finish before exiting)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MAX_ITERATIONS=0  # 0 = unlimited
DRY_RUN=false
PAUSE_SECONDS=5

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --pause)
      PAUSE_SECONDS="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--max N] [--dry-run] [--pause SECONDS]"
      exit 1
      ;;
  esac
done

# The prompt sent to each Claude Code session
TASK_PROMPT='Read .cortex-tasks/PROGRESS.md to find the next task. Then read that task in .cortex-tasks/TASKS.md for the full acceptance criteria. Implement the task, run the tests, update PROGRESS.md and TASKS.md, and commit your work. If all tasks are done, say "ALL TASKS COMPLETE" and exit.'

iteration=0
trap 'echo -e "\n\n⏹  Loop interrupted after $iteration iterations. Work is saved."; exit 0' INT

echo "═══════════════════════════════════════════════════"
echo "  Cortex Dev Loop"
echo "  Project: $PROJECT_DIR"
echo "  Max iterations: ${MAX_ITERATIONS:-unlimited}"
echo "═══════════════════════════════════════════════════"
echo ""

while true; do
  iteration=$((iteration + 1))

  # Check iteration limit
  if [[ $MAX_ITERATIONS -gt 0 && $iteration -gt $MAX_ITERATIONS ]]; then
    echo "✅ Reached max iterations ($MAX_ITERATIONS). Stopping."
    break
  fi

  echo "───────────────────────────────────────────────────"
  echo "  Iteration $iteration — $(date '+%Y-%m-%d %H:%M:%S')"
  echo "───────────────────────────────────────────────────"

  # Check if all tasks are done
  if grep -q "Next task:.*none\|ALL TASKS COMPLETE" "$PROJECT_DIR/.cortex-tasks/PROGRESS.md" 2>/dev/null; then
    echo "✅ All tasks complete! Exiting loop."
    break
  fi

  # Show current state
  echo ""
  echo "Current progress:"
  head -10 "$PROJECT_DIR/.cortex-tasks/PROGRESS.md" | grep -E "Last completed|Next task|Session" || true
  echo ""

  if $DRY_RUN; then
    echo "[DRY RUN] Would run: claude --print \"$TASK_PROMPT\""
    echo ""
    break
  fi

  # Run Claude Code
  # Using --print to run non-interactively. Claude reads the task, does the work, exits.
  cd "$PROJECT_DIR"
  claude --print "$TASK_PROMPT" || {
    echo "⚠  Claude session exited with error. Pausing before retry..."
    sleep 10
    continue
  }

  echo ""
  echo "✅ Session complete. Pausing ${PAUSE_SECONDS}s before next iteration..."
  sleep "$PAUSE_SECONDS"
done

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Loop finished after $iteration iterations"
echo "═══════════════════════════════════════════════════"
