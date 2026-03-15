#!/usr/bin/env bash
# =============================================================================
# Cortex Docker Entrypoint
# =============================================================================
# Runs on every container start. Handles first-run initialization:
#   1. Validates that the vault volume is mounted and readable
#   2. Scaffolds vault folder structure if the vault is empty
#   3. Builds indexes if data/ is missing or empty
#   4. Warms up the embedding model (loads into memory once)
#   5. Hands off to the MCP server (or whatever CMD was passed)
#
# Environment variables:
#   CORTEX_VAULT_PATH  Path to vault inside container (default: /app/vault)
#   CORTEX_DATA_PATH   Path to data dir inside container (default: /app/data)
#
# See docs/02-ARCHITECTURE.md § 6a for full Docker design.
# =============================================================================

set -euo pipefail

VAULT_PATH="${CORTEX_VAULT_PATH:-/app/vault}"
DATA_PATH="${CORTEX_DATA_PATH:-/app/data}"

log() { echo "[cortex-entrypoint] $*" >&2; }

# ---------------------------------------------------------------------------
# 1. Validate vault mount
# ---------------------------------------------------------------------------
if [ ! -d "$VAULT_PATH" ]; then
    log "ERROR: Vault directory not found at $VAULT_PATH"
    log "Make sure you've mounted your vault:"
    log "  docker run -v /path/to/your/vault:$VAULT_PATH ..."
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. First-run: scaffold vault structure if empty
# ---------------------------------------------------------------------------
if [ ! -d "$VAULT_PATH/00-inbox" ]; then
    log "No vault structure found — scaffolding..."
    uv run python -c "
from pathlib import Path
from cortex.vault.manager import scaffold_vault
scaffold_vault(Path('$VAULT_PATH'))
"
    log "Vault scaffolded successfully."
fi

# ---------------------------------------------------------------------------
# 3. First-run: build indexes if data dir is empty
# ---------------------------------------------------------------------------
if [ ! -f "$DATA_PATH/cortex.duckdb" ]; then
    log "No indexes found — will build on first use."
    mkdir -p "$DATA_PATH"
    # Index rebuild will be triggered by the MCP server on first query
    # once the indexing modules are implemented (Sessions 4-5)
fi

# ---------------------------------------------------------------------------
# 4. Warm up embedding model
# ---------------------------------------------------------------------------
log "Warming up embedding model..."
uv run python -c "
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')
    print('[cortex-entrypoint] Model loaded successfully.', flush=True)
except Exception as e:
    print(f'[cortex-entrypoint] Model warm-up skipped: {e}', flush=True)
" 2>&1 | head -5 || log "Model warm-up skipped (will load on first use)."

# ---------------------------------------------------------------------------
# 5. Hand off to CMD
# ---------------------------------------------------------------------------
log "Starting Cortex MCP server..."
exec "$@"
