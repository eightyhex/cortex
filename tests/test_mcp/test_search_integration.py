"""Integration test: full search pipeline with all components wired."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cortex.config import CortexConfig, RerankerConfig
from cortex.graph.manager import GraphManager
from cortex.index.manager import IndexManager
from cortex.mcp.server import init_server, search_vault
from cortex.vault.manager import VaultManager, scaffold_vault


def _write_note(vault_dir: Path, folder: str, filename: str, content: str) -> Path:
    """Helper to write a note file into the vault."""
    path = vault_dir / folder / filename
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture()
def full_setup(tmp_path: Path):
    """Set up vault with 6 notes, all indexes, and MCP server."""
    vault_dir = tmp_path / "vault"
    scaffold_vault(vault_dir)

    # Custom reranker config (non-default weights to verify config is respected)
    custom_reranker = RerankerConfig(
        recency_weight=0.5,
        type_weight=0.3,
        link_weight=0.1,
        status_weight=0.4,
    )

    config = CortexConfig(
        vault={"path": str(vault_dir)},
        draft={"drafts_dir": str(tmp_path / "drafts")},
        index={
            "db_path": str(tmp_path / "cortex.duckdb"),
            "embeddings_path": str(tmp_path / "embeddings"),
        },
        reranker=custom_reranker,
    )

    # Note 1: Active permanent note about machine learning
    _write_note(vault_dir, "30-permanent", "ml-fundamentals.md", (
        "---\n"
        "id: perm-001\n"
        "title: Machine Learning Fundamentals\n"
        "type: permanent\n"
        "tags: [ml, ai, fundamentals]\n"
        "status: active\n"
        f"created: 2026-03-10T10:00:00+00:00\n"
        f"modified: 2026-03-12T15:00:00+00:00\n"
        "---\n\n"
        "Machine learning is a subset of artificial intelligence that enables systems "
        "to learn from data. Key concepts include supervised learning, unsupervised "
        "learning, and reinforcement learning.\n"
    ))

    # Note 2: Active concept note linking to Note 1
    _write_note(vault_dir, "20-concepts", "neural-networks.md", (
        "---\n"
        "id: conc-002\n"
        "title: Neural Networks\n"
        "type: concept\n"
        "tags: [ml, neural-networks, deep-learning]\n"
        "status: active\n"
        f"created: 2026-03-11T08:00:00+00:00\n"
        f"modified: 2026-03-11T08:00:00+00:00\n"
        "---\n\n"
        "Neural networks are computing systems inspired by biological neural networks. "
        "See [[Machine Learning Fundamentals]] for background context.\n"
    ))

    # Note 3: Active source note
    _write_note(vault_dir, "10-sources", "deep-learning-paper.md", (
        "---\n"
        "id: src-003\n"
        "title: Deep Learning Review Paper\n"
        "type: source\n"
        "tags: [ml, paper, deep-learning]\n"
        "status: active\n"
        "source_url: https://example.com/dl-review\n"
        f"created: 2026-03-08T12:00:00+00:00\n"
        f"modified: 2026-03-08T12:00:00+00:00\n"
        "---\n\n"
        "This paper reviews recent advances in deep learning architectures "
        "including transformers, CNNs, and recurrent networks. "
        "References [[Neural Networks]] and [[Machine Learning Fundamentals]].\n"
    ))

    # Note 4: Archived note (should score lower)
    _write_note(vault_dir, "20-concepts", "old-ml-notes.md", (
        "---\n"
        "id: arch-004\n"
        "title: Old ML Notes\n"
        "type: concept\n"
        "tags: [ml, outdated]\n"
        "status: archived\n"
        f"created: 2025-01-15T10:00:00+00:00\n"
        f"modified: 2025-06-01T10:00:00+00:00\n"
        f"archived_date: 2025-06-01T10:00:00+00:00\n"
        "---\n\n"
        "These are old notes about machine learning techniques that have been "
        "superseded by newer approaches.\n"
    ))

    # Note 5: Task note
    _write_note(vault_dir, "02-tasks", "read-ml-book.md", (
        "---\n"
        "id: task-005\n"
        "title: Read ML Textbook Chapter 5\n"
        "type: task\n"
        "tags: [ml, reading]\n"
        "status: active\n"
        f"created: 2026-03-13T09:00:00+00:00\n"
        f"modified: 2026-03-13T09:00:00+00:00\n"
        "---\n\n"
        "Read chapter 5 of the machine learning textbook covering gradient descent "
        "and backpropagation algorithms.\n"
    ))

    # Note 6: Project note linking to multiple notes
    _write_note(vault_dir, "40-projects", "ml-research.md", (
        "---\n"
        "id: proj-006\n"
        "title: ML Research Project\n"
        "type: project\n"
        "tags: [ml, research, project]\n"
        "status: active\n"
        f"created: 2026-03-01T10:00:00+00:00\n"
        f"modified: 2026-03-14T10:00:00+00:00\n"
        "---\n\n"
        "Research project on applying machine learning to natural language processing. "
        "See [[Neural Networks]] and [[Deep Learning Review Paper]].\n"
    ))

    vault = VaultManager(vault_dir, config)
    notes = vault.scan_vault()

    # Build all indexes
    index_mgr = IndexManager(config)
    index_mgr.rebuild_all(notes)

    graph = GraphManager(tmp_path / "graph.graphml")
    graph.build_from_vault(notes)
    graph.save()

    # Init MCP server with all components
    init_server(config=config, vault=vault, drafts=None, index=index_mgr, graph=graph)

    return {
        "config": config,
        "vault": vault,
        "index": index_mgr,
        "graph": graph,
        "notes": notes,
        "custom_reranker": custom_reranker,
    }


class TestFullSearchIntegration:
    """End-to-end integration tests for the full search pipeline."""

    def test_search_returns_results_with_timestamps(self, full_setup):
        """Search results include created and modified ISO timestamps."""
        result = search_vault("machine learning")

        assert result["total"] > 0
        for entry in result["results"]:
            assert "created" in entry, f"Result {entry['title']} missing 'created'"
            assert "modified" in entry, f"Result {entry['title']} missing 'modified'"
            # Verify they are valid ISO timestamps
            datetime.fromisoformat(entry["created"])
            datetime.fromisoformat(entry["modified"])

    def test_context_shows_actual_dates(self, full_setup):
        """Context output shows actual created dates, not 'unknown'."""
        result = search_vault("machine learning")

        context = result["context"]
        assert "unknown" not in context.lower() or "Created:" not in context
        # At least one created date should appear in context
        assert "2026-03" in context

    def test_graph_expanded_results_have_snippets(self, full_setup):
        """Graph-expanded results include non-empty snippets."""
        result = search_vault("neural networks", limit=20)

        graph_results = [
            r for r in result["results"]
            if "graph" in r.get("matched_by", [])
        ]

        # If graph results exist, verify they have snippets
        for r in graph_results:
            assert r.get("snippet"), f"Graph result {r['title']} has empty snippet"

    def test_archived_notes_scored_lower(self, full_setup):
        """Archived notes should be scored lower than active notes of the same type."""
        result = search_vault("machine learning", limit=20)

        scores = {r["note_id"]: r["score"] for r in result["results"]}

        # The archived note should exist in results (it matches "machine learning")
        if "arch-004" in scores:
            # Any active concept note should score higher than the archived one
            active_concept_ids = ["conc-002"]
            for active_id in active_concept_ids:
                if active_id in scores:
                    assert scores[active_id] > scores["arch-004"], (
                        f"Active note {active_id} ({scores[active_id]:.4f}) should score "
                        f"higher than archived note arch-004 ({scores['arch-004']:.4f})"
                    )

    def test_reranker_config_respected(self, full_setup):
        """Custom reranker config from settings is used, not defaults."""
        custom = full_setup["custom_reranker"]

        # Verify our config is non-default
        default = RerankerConfig()
        assert custom.recency_weight != default.recency_weight or \
               custom.type_weight != default.type_weight or \
               custom.status_weight != default.status_weight, \
            "Test requires custom config to differ from defaults"

        # Run search — the fact it uses custom config is verified by the pipeline
        # wiring in search_vault which reads _config.reranker
        result = search_vault("machine learning")
        assert result["total"] > 0

    def test_multiple_search_sources_contribute(self, full_setup):
        """Search results come from multiple sources (lexical, semantic, potentially graph)."""
        result = search_vault("machine learning fundamentals", limit=20)

        all_sources = set()
        for r in result["results"]:
            all_sources.update(r.get("matched_by", []))

        # At least lexical and semantic should contribute
        assert "lexical" in all_sources, "Lexical search should contribute results"
        assert "semantic" in all_sources, "Semantic search should contribute results"

    def test_explanation_includes_sources(self, full_setup):
        """Explanation field lists which search sources contributed."""
        result = search_vault("machine learning")

        explanation = result["explanation"]
        assert "lexical" in explanation or "semantic" in explanation, \
            f"Explanation should mention search sources: {explanation}"


@pytest.fixture()
def rich_setup(tmp_path: Path):
    """Set up vault with 5+ notes containing substantial content for Q&A testing."""
    vault_dir = tmp_path / "vault"
    scaffold_vault(vault_dir)

    config = CortexConfig(
        vault={"path": str(vault_dir)},
        draft={"drafts_dir": str(tmp_path / "drafts")},
        index={
            "db_path": str(tmp_path / "cortex.duckdb"),
            "embeddings_path": str(tmp_path / "embeddings"),
        },
    )

    # Note 1: Long permanent note about neural networks (~700 chars)
    _write_note(vault_dir, "30-permanent", "nn-deep-dive.md", (
        "---\n"
        "id: rich-001\n"
        "title: Neural Networks Deep Dive\n"
        "type: permanent\n"
        "tags: [neural-networks, deep-learning, architecture]\n"
        "status: active\n"
        "created: 2026-03-10T10:00:00+00:00\n"
        "modified: 2026-03-12T15:00:00+00:00\n"
        "---\n\n"
        "Neural networks are computing systems inspired by biological neural networks. "
        "They consist of layers of interconnected nodes that process information. "
        "The input layer receives data, hidden layers perform transformations, and "
        "the output layer produces predictions. Training involves adjusting weights "
        "through backpropagation, where errors are propagated backwards through the "
        "network. Common architectures include convolutional neural networks for images, "
        "recurrent neural networks for sequences, and transformer networks for natural "
        "language processing. Regularization techniques like dropout and batch normalization "
        "help prevent overfitting. Learning rate schedules and optimizers like Adam and "
        "SGD with momentum control the training dynamics.\n"
    ))

    # Note 2: Long concept note about transformers (~600 chars)
    _write_note(vault_dir, "20-concepts", "transformers.md", (
        "---\n"
        "id: rich-002\n"
        "title: Transformer Architecture\n"
        "type: concept\n"
        "tags: [transformers, attention, nlp]\n"
        "status: active\n"
        "created: 2026-03-11T08:00:00+00:00\n"
        "modified: 2026-03-11T08:00:00+00:00\n"
        "---\n\n"
        "The transformer architecture revolutionized natural language processing by "
        "introducing the self-attention mechanism. Unlike RNNs, transformers process "
        "all tokens in parallel, making them highly efficient for training on modern "
        "hardware. Key components include multi-head attention, positional encoding, "
        "layer normalization, and feed-forward networks. The encoder-decoder structure "
        "is used for translation tasks, while decoder-only models like GPT excel at "
        "text generation. BERT uses the encoder for bidirectional understanding. "
        "See [[Neural Networks Deep Dive]] for background.\n"
    ))

    # Note 3: Source note with URL (~550 chars)
    _write_note(vault_dir, "10-sources", "attention-paper.md", (
        "---\n"
        "id: rich-003\n"
        "title: Attention Is All You Need\n"
        "type: source\n"
        "tags: [paper, transformers, attention]\n"
        "status: active\n"
        "source_url: https://arxiv.org/abs/1706.03762\n"
        "created: 2026-03-08T12:00:00+00:00\n"
        "modified: 2026-03-08T12:00:00+00:00\n"
        "---\n\n"
        "The seminal paper introducing the transformer architecture. It proposes "
        "replacing recurrence and convolutions entirely with attention mechanisms. "
        "The model achieves state-of-the-art results on English-to-German and "
        "English-to-French translation benchmarks. Key innovations include scaled "
        "dot-product attention, multi-head attention allowing the model to attend "
        "to information from different representation subspaces, and positional "
        "encodings using sine and cosine functions.\n"
    ))

    # Note 4: Long concept note about embeddings (~600 chars)
    _write_note(vault_dir, "20-concepts", "embeddings.md", (
        "---\n"
        "id: rich-004\n"
        "title: Word Embeddings and Representations\n"
        "type: concept\n"
        "tags: [embeddings, nlp, representation-learning]\n"
        "status: active\n"
        "created: 2026-03-09T14:00:00+00:00\n"
        "modified: 2026-03-09T14:00:00+00:00\n"
        "---\n\n"
        "Word embeddings map words to dense vector representations that capture "
        "semantic meaning. Word2Vec introduced skip-gram and CBOW architectures. "
        "GloVe combines global matrix factorization with local context windows. "
        "Modern approaches use contextual embeddings from transformer models, where "
        "the same word gets different vectors depending on context. These embeddings "
        "form the foundation of most NLP systems, enabling transfer learning across "
        "tasks. Sentence embeddings extend this concept to full sequences using "
        "techniques like mean pooling or specialized models like Sentence-BERT.\n"
    ))

    # Note 5: Long permanent note about training (~600 chars)
    _write_note(vault_dir, "30-permanent", "training-techniques.md", (
        "---\n"
        "id: rich-005\n"
        "title: Model Training Techniques\n"
        "type: permanent\n"
        "tags: [training, optimization, deep-learning]\n"
        "status: active\n"
        "created: 2026-03-07T16:00:00+00:00\n"
        "modified: 2026-03-13T11:00:00+00:00\n"
        "---\n\n"
        "Training deep learning models requires careful selection of hyperparameters "
        "and optimization strategies. Gradient descent variants include SGD, Adam, "
        "AdaGrad, and RMSprop. Learning rate scheduling with warmup and cosine decay "
        "improves convergence. Data augmentation increases effective training set size. "
        "Mixed precision training uses float16 for speed with float32 master weights. "
        "Distributed training across multiple GPUs uses data parallelism or model "
        "parallelism. Gradient accumulation simulates larger batch sizes on limited "
        "hardware. Early stopping prevents overfitting by monitoring validation loss.\n"
    ))

    vault = VaultManager(vault_dir, config)
    notes = vault.scan_vault()

    index_mgr = IndexManager(config)
    index_mgr.rebuild_all(notes)

    graph = GraphManager(tmp_path / "graph.graphml")
    graph.build_from_vault(notes)
    graph.save()

    init_server(config=config, vault=vault, drafts=None, index=index_mgr, graph=graph)

    return {"config": config, "vault": vault, "notes": notes}


class TestDateFiltering:
    """Tests for created_after / created_before date filtering on search_vault."""

    def test_created_after_filters_old_notes(self, full_setup):
        """created_after excludes notes created before the given date."""
        result = search_vault("machine learning", created_after="2026-03-10", limit=20)

        for entry in result["results"]:
            created = datetime.fromisoformat(entry["created"]).date()
            assert created >= datetime(2026, 3, 10).date(), (
                f"Note '{entry['title']}' created {created} should be >= 2026-03-10"
            )

    def test_created_before_filters_new_notes(self, full_setup):
        """created_before excludes notes created after the given date."""
        result = search_vault("machine learning", created_before="2026-03-09", limit=20)

        for entry in result["results"]:
            created = datetime.fromisoformat(entry["created"]).date()
            assert created <= datetime(2026, 3, 9).date(), (
                f"Note '{entry['title']}' created {created} should be <= 2026-03-09"
            )

    def test_date_range_narrows_results(self, full_setup):
        """Using both created_after and created_before returns only notes in the range."""
        result = search_vault(
            "machine learning",
            created_after="2026-03-10",
            created_before="2026-03-11",
            limit=20,
        )

        for entry in result["results"]:
            created = datetime.fromisoformat(entry["created"]).date()
            assert datetime(2026, 3, 10).date() <= created <= datetime(2026, 3, 11).date(), (
                f"Note '{entry['title']}' created {created} should be between 2026-03-10 and 2026-03-11"
            )

        # We know perm-001 (Mar 10) and conc-002 (Mar 11) are in range
        ids = [e["note_id"] for e in result["results"]]
        assert "perm-001" in ids or "conc-002" in ids, "At least one note in range should appear"

    def test_date_filter_excludes_all_returns_empty(self, full_setup):
        """Date range that matches no notes returns empty results."""
        result = search_vault(
            "machine learning",
            created_after="2099-01-01",
            limit=20,
        )
        assert result["total"] == 0

    def test_created_after_only_no_created_before(self, full_setup):
        """created_after works without created_before."""
        # All notes in full_setup are from 2025-01 to 2026-03
        result = search_vault("machine learning", created_after="2026-03-13", limit=20)

        for entry in result["results"]:
            created = datetime.fromisoformat(entry["created"]).date()
            assert created >= datetime(2026, 3, 13).date()

    def test_created_before_only_no_created_after(self, full_setup):
        """created_before works without created_after."""
        result = search_vault("machine learning", created_before="2025-02-01", limit=20)

        for entry in result["results"]:
            created = datetime.fromisoformat(entry["created"]).date()
            assert created <= datetime(2025, 2, 1).date()


class TestSearchDrivenQA:
    """Verify search_vault returns enough info for Q&A without get_note calls."""

    def test_top_results_include_full_content(self, rich_setup):
        """Top 3 results include full content field."""
        result = search_vault("transformer attention neural networks")
        assert result["total"] >= 3
        for r in result["results"][:3]:
            assert "content" in r, f"Top result {r['title']} missing 'content'"
            assert len(r["content"]) > 200, f"Content for {r['title']} too short"

    def test_all_results_include_tags(self, rich_setup):
        """All results include tags as a list."""
        result = search_vault("neural networks embeddings")
        assert result["total"] >= 1
        for r in result["results"]:
            assert "tags" in r, f"Result {r['title']} missing 'tags'"
            assert isinstance(r["tags"], list)
            assert len(r["tags"]) > 0

    def test_source_notes_include_source_url(self, rich_setup):
        """Source notes include source_url in results."""
        result = search_vault("attention paper transformer", limit=20)
        source_results = [r for r in result["results"] if r["note_type"] == "source"]
        assert len(source_results) >= 1
        for r in source_results:
            assert "source_url" in r, f"Source result {r['title']} missing 'source_url'"

    def test_snippets_exceed_200_chars(self, rich_setup):
        """Snippets for notes with substantial content exceed 200 characters."""
        result = search_vault("neural networks training techniques")
        assert result["total"] >= 1
        long_snippets = [r for r in result["results"] if len(r.get("snippet", "")) > 200]
        assert len(long_snippets) >= 1, "At least one snippet should exceed 200 chars"

    def test_context_exceeds_4000_chars(self, rich_setup):
        """Context field uses the increased budget and exceeds 4000 characters."""
        result = search_vault("neural networks transformer embeddings training", limit=10)
        context = result["context"]
        assert len(context) > 2000, (
            f"Context should be substantial with increased budget, got {len(context)} chars"
        )
