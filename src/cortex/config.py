"""Cortex configuration module.

Loads settings from settings.yaml (or settings.example.yaml as fallback)
with environment variable overrides via pydantic-settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VaultConfig(BaseModel):
    path: Path = Path("./vault")
    templates_folder: str = "_templates"


class IndexConfig(BaseModel):
    db_path: Path = Path("./data/cortex.duckdb")
    embeddings_path: Path = Path("./data/embeddings")
    graph_path: Path = Path("./data/graph")


class EmbeddingsConfig(BaseModel):
    model: str = "nomic-embed-text"
    chunk_size: int = 300
    chunk_max: int = 500
    dimension: int = 768


class SearchConfig(BaseModel):
    default_limit: int = 10
    fusion_k: int = 60


class StalenessThresholds(BaseModel):
    inbox: int = 30
    task: int = 30
    source: int = 90
    concept: int = 365
    permanent: int = 365


class LifecycleConfig(BaseModel):
    staleness_thresholds: StalenessThresholds = Field(default_factory=StalenessThresholds)


class DraftConfig(BaseModel):
    drafts_dir: Path = Path("./data/drafts")
    stale_draft_hours: int = 24


class RerankerConfig(BaseModel):
    recency_weight: float = 0.15
    type_weight: float = 0.10
    link_weight: float = 0.10
    status_weight: float = 0.10
    recency_halflife_days: int = 90


class McpConfig(BaseModel):
    tool_timeout: int = 30
    max_context_tokens: int = 8000


def _load_yaml_settings() -> dict[str, Any]:
    """Load settings from settings.yaml, falling back to settings.example.yaml."""
    for filename in ("settings.yaml", "settings.example.yaml"):
        path = Path(filename)
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
            return data if data else {}
    return {}


class CortexConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CORTEX_",
        env_nested_delimiter="__",
    )

    vault: VaultConfig = Field(default_factory=VaultConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    lifecycle: LifecycleConfig = Field(default_factory=LifecycleConfig)
    draft: DraftConfig = Field(default_factory=DraftConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                   dotenv_settings, file_secret_settings):
        """Load from init args first, then env vars, then YAML file."""
        from pydantic_settings import PydanticBaseSettingsSource

        class YamlSettingsSource(PydanticBaseSettingsSource):
            def get_field_value(self, field, field_name):
                yaml_data = _load_yaml_settings()
                value = yaml_data.get(field_name)
                return value, field_name, False

            def __call__(self):
                return _load_yaml_settings()

        return (
            init_settings,
            env_settings,
            YamlSettingsSource(settings_cls),
        )
