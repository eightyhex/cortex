"""Tests for HeuristicReranker — heuristic-based post-fusion reranking."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cortex.config import RerankerConfig
from cortex.graph.manager import GraphManager
from cortex.index.lexical import LexicalIndex
from cortex.query.pipeline import RankedResult
from cortex.query.reranker import HeuristicReranker
from cortex.vault.parser import Link, Note


def _make_note(
    note_id: str,
    title: str,
    content: str,
    note_type: str = "concept",
    status: str = "active",
    created: datetime | None = None,
    tags: list[str] | None = None,
    links: list[Link] | None = None,
) -> Note:
    created = created or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Note(
        id=note_id,
        title=title,
        note_type=note_type,
        path=Path(f"20-concepts/{note_id}.md"),
        content=content,
        frontmatter={"status": status},
        created=created,
        modified=created,
        tags=tags or [],
        links=links or [],
        status=status,
    )


def _make_ranked(note_id: str, title: str, score: float, note_type: str = "concept") -> RankedResult:
    return RankedResult(
        note_id=note_id,
        title=title,
        score=score,
        matched_by=["lexical"],
        snippet="some snippet",
        note_type=note_type,
    )


@pytest.fixture
def lexical(tmp_path):
    return LexicalIndex(tmp_path / "test.duckdb")


@pytest.fixture
def graph(tmp_path):
    return GraphManager(tmp_path / "test.graphml")


@pytest.fixture
def config():
    return RerankerConfig()


def test_recency_boost(lexical, config):
    """Newer notes should be boosted higher than older ones."""
    # Recent note (created 1 day ago)
    recent = _make_note("n1", "Recent Note", "content", created=datetime(2026, 3, 14, tzinfo=timezone.utc))
    # Old note (created 1 year ago)
    old = _make_note("n2", "Old Note", "content", created=datetime(2025, 3, 15, tzinfo=timezone.utc))

    lexical.index_note(recent)
    lexical.index_note(old)

    # Both start with equal scores
    results = [
        _make_ranked("n1", "Recent Note", 0.5),
        _make_ranked("n2", "Old Note", 0.5),
    ]

    reranker = HeuristicReranker(config, lexical)
    reranked = reranker.rerank(results, "test query")

    # Recent note should have higher score
    assert reranked[0].note_id == "n1"
    assert reranked[0].score > reranked[1].score


def test_type_boost(lexical, config):
    """Permanent notes should rank higher than inbox notes, all else equal."""
    permanent = _make_note("n1", "Permanent Note", "content", note_type="permanent")
    inbox = _make_note("n2", "Inbox Note", "content", note_type="inbox")

    lexical.index_note(permanent)
    lexical.index_note(inbox)

    results = [
        _make_ranked("n2", "Inbox Note", 0.5, note_type="inbox"),
        _make_ranked("n1", "Permanent Note", 0.5, note_type="permanent"),
    ]

    reranker = HeuristicReranker(config, lexical)
    reranked = reranker.rerank(results, "test query")

    # Permanent note should rank first
    assert reranked[0].note_id == "n1"
    assert reranked[0].score > reranked[1].score


def test_link_density_boost(lexical, graph, config):
    """Notes with more inbound links should be boosted."""
    # Create notes
    popular = _make_note("n1", "Popular Note", "content")
    lonely = _make_note("n2", "Lonely Note", "content")
    linker1 = _make_note("n3", "Linker 1", "content",
                         links=[Link(source_id="n3", target_id="n1", target_title="Popular Note", link_type="wikilink")])
    linker2 = _make_note("n4", "Linker 2", "content",
                         links=[Link(source_id="n4", target_id="n1", target_title="Popular Note", link_type="wikilink")])

    lexical.index_note(popular)
    lexical.index_note(lonely)

    # Build graph with links pointing to n1
    graph.build_from_vault([popular, lonely, linker1, linker2])

    results = [
        _make_ranked("n1", "Popular Note", 0.5),
        _make_ranked("n2", "Lonely Note", 0.5),
    ]

    reranker = HeuristicReranker(config, lexical)
    reranked = reranker.rerank(results, "test query", graph=graph)

    # Popular note (2 inbound links) should rank higher
    assert reranked[0].note_id == "n1"
    assert reranked[0].score > reranked[1].score


def test_status_penalty(lexical, config):
    """Archived notes should receive lower status boost than active ones."""
    active = _make_note("n1", "Active Note", "content", status="active")
    archived = _make_note("n2", "Archived Note", "content", status="archived")

    lexical.index_note(active)
    lexical.index_note(archived)

    results = [
        _make_ranked("n1", "Active Note", 0.5),
        _make_ranked("n2", "Archived Note", 0.5),
    ]

    reranker = HeuristicReranker(config, lexical)
    reranked = reranker.rerank(results, "test query")

    # Active note should rank higher due to status boost
    assert reranked[0].note_id == "n1"
    assert reranked[0].score > reranked[1].score


def test_empty_results(lexical, config):
    """Reranking empty list returns empty list."""
    reranker = HeuristicReranker(config, lexical)
    assert reranker.rerank([], "test query") == []


def test_configurable_weights(lexical):
    """Custom weights should change reranking behavior."""
    # Zero out all weights except type
    config = RerankerConfig(
        recency_weight=0.0,
        type_weight=1.0,
        link_weight=0.0,
        status_weight=0.0,
    )

    permanent = _make_note("n1", "Permanent", "content", note_type="permanent")
    inbox = _make_note("n2", "Inbox", "content", note_type="inbox")

    lexical.index_note(permanent)
    lexical.index_note(inbox)

    results = [
        _make_ranked("n2", "Inbox", 0.5, note_type="inbox"),
        _make_ranked("n1", "Permanent", 0.5, note_type="permanent"),
    ]

    reranker = HeuristicReranker(config, lexical)
    reranked = reranker.rerank(results, "test query")

    # With only type_weight=1.0: permanent gets +1.0, inbox gets +0.1
    assert reranked[0].note_id == "n1"
    assert reranked[0].score == pytest.approx(0.5 + 1.0, abs=0.01)
    assert reranked[1].score == pytest.approx(0.5 + 0.1, abs=0.01)


def test_scores_always_increase(lexical, config):
    """Reranking should only increase scores (boosts are non-negative)."""
    note = _make_note("n1", "Test Note", "content")
    lexical.index_note(note)

    results = [_make_ranked("n1", "Test Note", 0.5)]

    reranker = HeuristicReranker(config, lexical)
    reranked = reranker.rerank(results, "test query")

    assert reranked[0].score >= results[0].score


def test_no_graph_still_works(lexical, config):
    """Reranker works without a graph (graph=None)."""
    note = _make_note("n1", "Test", "content")
    lexical.index_note(note)

    results = [_make_ranked("n1", "Test", 0.5)]

    reranker = HeuristicReranker(config, lexical)
    reranked = reranker.rerank(results, "query", graph=None)

    assert len(reranked) == 1
    assert reranked[0].note_id == "n1"
