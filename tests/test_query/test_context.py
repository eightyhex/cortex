"""Tests for the Context Assembler."""

from datetime import datetime
from pathlib import Path

from cortex.query.context import ContextAssembler
from cortex.query.fusion import FusedResult
from cortex.vault.parser import Link, Note


def _make_fused(
    note_id: str,
    title: str = "",
    score: float = 0.5,
    snippet: str = "",
    matched_by: list[str] | None = None,
) -> FusedResult:
    return FusedResult(
        note_id=note_id,
        title=title or f"Note {note_id}",
        score=score,
        snippet=snippet or f"Content about {note_id}",
        note_type="concept",
        path=f"20-concepts/{note_id}.md",
        matched_by=matched_by or ["lexical"],
    )


def _make_note(
    note_id: str,
    title: str = "",
    tags: list[str] | None = None,
    links: list[Link] | None = None,
    superseded_by: str | None = None,
) -> Note:
    return Note(
        id=note_id,
        title=title or f"Note {note_id}",
        note_type="concept",
        path=Path(f"20-concepts/{note_id}.md"),
        content="",
        frontmatter={},
        created=datetime(2026, 1, 15),
        modified=datetime(2026, 1, 15),
        tags=tags or [],
        links=links or [],
        superseded_by=superseded_by,
    )


class TestContextAssembler:
    """Tests for ContextAssembler.assemble()."""

    def test_basic_assembly(self):
        """Assembles header and result blocks with metadata."""
        results = [
            _make_fused("n1", "Machine Learning Basics", 0.8, "ML is a subset of AI.", ["lexical", "semantic"]),
            _make_fused("n2", "Neural Networks", 0.6, "Neural nets learn patterns.", ["semantic"]),
        ]
        notes = {
            "n1": _make_note("n1", "Machine Learning Basics", tags=["ml", "ai"]),
            "n2": _make_note(
                "n2",
                "Neural Networks",
                tags=["nn"],
                links=[Link("n2", "n1", "Machine Learning Basics", "wikilink")],
            ),
        }

        assembler = ContextAssembler()
        output = assembler.assemble(results, "what is machine learning?", notes=notes)

        # Header
        assert "## Query: what is machine learning?" in output
        assert "## Retrieved 2 results" in output
        assert "lexical" in output
        assert "semantic" in output

        # Result blocks
        assert "### Result 1: Machine Learning Basics" in output
        assert "score: 0.8000" in output
        assert "ML is a subset of AI." in output
        assert "Tags: ml, ai" in output
        assert "Created: 2026-01-15" in output

        assert "### Result 2: Neural Networks" in output
        assert "Links: Machine Learning Basics" in output

    def test_empty_results(self):
        """Empty results produce a 'no results' message."""
        assembler = ContextAssembler()
        output = assembler.assemble([], "missing topic")

        assert "## Query: missing topic" in output
        assert "Retrieved 0 results" in output
        assert "No results found." in output

    def test_truncation_respects_max_tokens(self):
        """Long excerpts are truncated to fit within max_tokens budget."""
        long_snippet = "word " * 2000  # ~10000 chars / ~2500 tokens
        results = [_make_fused("n1", snippet=long_snippet)]

        assembler = ContextAssembler()
        output = assembler.assemble(results, "test query", max_tokens=200)

        # Output should be significantly shorter than the full snippet
        output_tokens_estimate = len(output) // 4
        assert output_tokens_estimate <= 250  # some slack for rounding
        assert "..." in output  # truncation marker

    def test_superseded_annotation(self):
        """Superseded notes get a warning annotation."""
        results = [_make_fused("old_note", "Old Concept", 0.5)]
        notes = {
            "old_note": _make_note("old_note", "Old Concept", superseded_by="new_note"),
            "new_note": _make_note("new_note", "New Concept"),
        }

        assembler = ContextAssembler()
        output = assembler.assemble(results, "some query", notes=notes)

        assert "\u26a0 This note was superseded by: New Concept (id: new_note)" in output

    def test_no_notes_metadata_fallback(self):
        """When no notes dict is provided, metadata fields show defaults."""
        results = [_make_fused("n1", "Some Note", 0.5)]

        assembler = ContextAssembler()
        output = assembler.assemble(results, "query")

        assert "Tags: none" in output
        assert "Links: none" in output
        assert "Created: unknown" in output

    def test_multiple_results_budget_exhaustion(self):
        """When budget runs out, later results are dropped."""
        results = [
            _make_fused(f"n{i}", snippet="x " * 500) for i in range(20)
        ]

        assembler = ContextAssembler()
        output = assembler.assemble(results, "test", max_tokens=300)

        # Should not contain all 20 results
        assert "### Result 20" not in output
        # But should contain at least the first result
        assert "### Result 1" in output
