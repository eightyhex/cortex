"""Tests for cortex.config module."""

from pathlib import Path

import pytest
import yaml


class TestCortexConfig:
    """Test CortexConfig loading and overrides."""

    def test_default_loading(self, tmp_path, monkeypatch):
        """CortexConfig loads defaults when no YAML file exists."""
        monkeypatch.chdir(tmp_path)

        import os
        for key in list(os.environ):
            if key.startswith("CORTEX_"):
                monkeypatch.delenv(key)

        from cortex.config import CortexConfig

        config = CortexConfig()

        assert config.vault.path == Path("./vault")
        assert config.vault.templates_folder == "_templates"
        assert config.index.db_path == Path("./data/cortex.duckdb")
        assert config.embeddings.model == "nomic-embed-text"
        assert config.embeddings.chunk_size == 300
        assert config.embeddings.dimension == 768
        assert config.search.default_limit == 10
        assert config.search.fusion_k == 60
        assert config.lifecycle.staleness_thresholds.inbox == 30
        assert config.lifecycle.staleness_thresholds.permanent == 365
        assert config.draft.drafts_dir == Path("./data/drafts")
        assert config.draft.stale_draft_hours == 24
        assert config.mcp.tool_timeout == 30
        assert config.mcp.max_context_tokens == 4000

    def test_yaml_loading(self, tmp_path, monkeypatch):
        """CortexConfig loads values from settings.yaml."""
        monkeypatch.chdir(tmp_path)

        settings = {
            "vault": {"path": "/custom/vault", "templates_folder": "my_templates"},
            "search": {"default_limit": 25},
            "embeddings": {"chunk_size": 512},
        }
        yaml_path = tmp_path / "settings.yaml"
        yaml_path.write_text(yaml.dump(settings))

        from cortex.config import CortexConfig

        config = CortexConfig()

        assert config.vault.path == Path("/custom/vault")
        assert config.vault.templates_folder == "my_templates"
        assert config.search.default_limit == 25
        assert config.embeddings.chunk_size == 512
        # Defaults still work for unset values
        assert config.embeddings.model == "nomic-embed-text"

    def test_example_yaml_fallback(self, tmp_path, monkeypatch):
        """CortexConfig falls back to settings.example.yaml when settings.yaml is missing."""
        monkeypatch.chdir(tmp_path)

        settings = {
            "vault": {"path": "/fallback/vault"},
        }
        example_path = tmp_path / "settings.example.yaml"
        example_path.write_text(yaml.dump(settings))

        from cortex.config import CortexConfig

        config = CortexConfig()

        assert config.vault.path == Path("/fallback/vault")

    def test_env_override(self, tmp_path, monkeypatch):
        """Environment variables override YAML and default values."""
        monkeypatch.chdir(tmp_path)

        # Write a YAML with one value
        settings = {"vault": {"path": "/yaml/vault"}}
        yaml_path = tmp_path / "settings.yaml"
        yaml_path.write_text(yaml.dump(settings))

        # Override with env var
        monkeypatch.setenv("CORTEX_VAULT__PATH", "/env/vault")

        from cortex.config import CortexConfig

        config = CortexConfig()

        # Env var should take precedence
        assert config.vault.path == Path("/env/vault")

    def test_missing_file_returns_defaults(self, tmp_path, monkeypatch):
        """When no YAML files exist, all defaults are used."""
        monkeypatch.chdir(tmp_path)

        from cortex.config import CortexConfig

        config = CortexConfig()

        # Should have all defaults without error
        assert config.vault.path == Path("./vault")
        assert config.index.embeddings_path == Path("./data/embeddings")
        assert config.lifecycle.staleness_thresholds.source == 90

    def test_vault_path_is_path_object(self, tmp_path, monkeypatch):
        """config.vault.path returns a Path object."""
        monkeypatch.chdir(tmp_path)

        from cortex.config import CortexConfig

        config = CortexConfig()
        assert isinstance(config.vault.path, Path)
