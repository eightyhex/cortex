"""Tests for health_check module."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.config import CortexConfig
from cortex.health import health_check


@pytest.fixture
def config_with_vault(tmp_path: Path) -> CortexConfig:
    """Config pointing to a real temp vault directory."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    return CortexConfig(vault={"path": str(vault_dir)}, index={"db_path": str(tmp_path / "test.duckdb")})


@pytest.fixture
def config_missing_vault(tmp_path: Path) -> CortexConfig:
    """Config pointing to a nonexistent vault directory."""
    return CortexConfig(vault={"path": str(tmp_path / "nonexistent")}, index={"db_path": str(tmp_path / "test.duckdb")})


def test_health_check_returns_dict(config_with_vault: CortexConfig):
    result = health_check(config_with_vault)
    assert isinstance(result, dict)
    assert "status" in result
    assert "checks" in result


def test_health_check_python_always_ok(config_with_vault: CortexConfig):
    result = health_check(config_with_vault)
    assert result["checks"]["python"]["status"] == "ok"


def test_health_check_vault_ok(config_with_vault: CortexConfig):
    result = health_check(config_with_vault)
    assert result["checks"]["vault"]["status"] == "ok"


def test_health_check_vault_missing(config_missing_vault: CortexConfig):
    result = health_check(config_missing_vault)
    assert result["checks"]["vault"]["status"] == "error"
    assert "volume mount" in result["checks"]["vault"]["error"]


def test_health_check_duckdb_accessible(config_with_vault: CortexConfig):
    result = health_check(config_with_vault)
    assert result["checks"]["duckdb"]["status"] == "ok"


def test_health_check_embedding_model_loaded(config_with_vault: CortexConfig):
    result = health_check(config_with_vault)
    assert result["checks"]["embedding_model"]["status"] == "ok"


def test_health_check_overall_healthy(config_with_vault: CortexConfig):
    result = health_check(config_with_vault)
    assert result["status"] == "healthy"


def test_health_check_overall_unhealthy_missing_vault(config_missing_vault: CortexConfig):
    result = health_check(config_missing_vault)
    assert result["status"] == "unhealthy"
