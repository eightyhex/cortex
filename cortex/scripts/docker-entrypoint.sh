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
    log "No vault structure found — scaffolding from vault.example/ ..."
    # TODO: implement in Session 1
    # uv run cortex init-vault --vault-path "$VAULT_PATH"
    log "(vault scaffolding not yet implemented — see Session 1)"
fi

# ---------------------------------------------------------------------------
# 3. First-run: build indexes if data dir is empty
# ---------------------------------------------------------------------------
if [ ! -f "$DATA_PATH/cortex.duckdb" ]; then
    log "No indexes found — building from vault (this may take a moment)..."
    mkdir -p "$DATA_PATH"
    # TODO: implement in Sessions 4-5
    # uv run cortex rebuild-index --vault-path "$VAULT_PATH" --data-path "$DATA_PATH"
    log "(index build not yet implemented — see Sessions 4-5)"
fi

# ---------------------------------------------------------------------------
# 4. Warm up embedding model
# ---------------------------------------------------------------------------
log "Warming up embedding model..."
# TODO: implement in Session 5
# python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')"

# ---------------------------------------------------------------------------
# 5. Hand off to CMD
# ---------------------------------------------------------------------------
log "Starting Cortex MCP server..."
exec "$@"
