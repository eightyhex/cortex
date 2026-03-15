"""Health check for Cortex services.

Reports status of: Python process, DuckDB accessibility, vault path
readability, and embedding model loaded state.
"""

from __future__ import annotations

from pathlib import Path

from cortex.config import CortexConfig


def health_check(config: CortexConfig | None = None) -> dict:
    """Return health status of all Cortex subsystems.

    Returns a dict with overall status ("healthy" / "degraded" / "unhealthy")
    and per-component checks.
    """
    config = config or CortexConfig()
    checks: dict[str, dict] = {}

    # 1. Python process — always ok if we got here
    checks["python"] = {"status": "ok"}

    # 2. Vault path readability
    vault_path = Path(config.vault.path).resolve()
    if vault_path.is_dir():
        try:
            list(vault_path.iterdir())
            checks["vault"] = {"status": "ok", "path": str(vault_path)}
        except PermissionError:
            checks["vault"] = {
                "status": "error",
                "path": str(vault_path),
                "error": "Vault directory exists but is not readable. Check file permissions.",
            }
    else:
        checks["vault"] = {
            "status": "error",
            "path": str(vault_path),
            "error": (
                "Vault directory not found. "
                "If running in Docker, check that the volume mount is correct "
                "(e.g., -v /path/to/vault:/app/vault)."
            ),
        }

    # 3. DuckDB accessibility
    db_path = Path(config.index.db_path).resolve()
    try:
        import duckdb

        # Try to open (or create) the database
        conn = duckdb.connect(str(db_path))
        conn.execute("SELECT 1")
        conn.close()
        checks["duckdb"] = {"status": "ok", "path": str(db_path)}
    except Exception as exc:
        checks["duckdb"] = {
            "status": "error",
            "path": str(db_path),
            "error": f"DuckDB not accessible: {exc}",
        }

    # 4. Embedding model loaded
    try:
        from cortex.index.models import EmbeddingModel

        model = EmbeddingModel()
        # Trigger lazy load with a tiny embedding
        model.embed("health check")
        checks["embedding_model"] = {"status": "ok", "model": model._model_name}
    except Exception as exc:
        checks["embedding_model"] = {
            "status": "error",
            "error": f"Embedding model failed to load: {exc}",
        }

    # Overall status
    statuses = [c["status"] for c in checks.values()]
    if all(s == "ok" for s in statuses):
        overall = "healthy"
    elif checks["python"]["status"] == "ok" and checks["vault"]["status"] == "ok":
        overall = "degraded"
    else:
        overall = "unhealthy"

    return {"status": overall, "checks": checks}
