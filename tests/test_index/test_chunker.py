"""Tests for semantic boundary chunker."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.index.chunker import Chunk, chunk_note
from cortex.vault.parser import Note


def _make_note(content: str, note_id: str = "test-note-id") -> Note:
    return Note(
        id=note_id,
        title="Test Note",
        note_type="permanent",
        path=Path("/vault/test.md"),
        content=content,
        frontmatter={},
        created=datetime(2026, 1, 1),
        modified=datetime(2026, 1, 1),
    )


def _mock_model(chars_per_token: int = 4) -> MagicMock:
    """Create a mock EmbeddingModel where token count ≈ len(text) / chars_per_token."""
    model = MagicMock()
    model.tokenize_count.side_effect = lambda text: max(1, len(text) // chars_per_token)
    return model


class TestChunkNote:
    def test_short_note_single_chunk(self):
        """A note shorter than target_tokens becomes a single chunk."""
        content = "This is a short note."
        note = _make_note(content)
        model = _mock_model()

        chunks = chunk_note(note, model, target_tokens=300, max_tokens=500)

        assert len(chunks) == 1
        assert chunks[0].text == content
        assert chunks[0].chunk_id == "test-note-id__chunk_0"
        assert chunks[0].note_id == "test-note-id"
        assert chunks[0].index == 0

    def test_long_note_splits_into_multiple_chunks(self):
        """A note with multiple paragraphs exceeding target_tokens splits into multiple chunks."""
        # Each paragraph is ~100 chars ≈ 25 tokens at 4 chars/token
        paragraphs = [f"Paragraph {i}. " + "x" * 90 for i in range(20)]
        content = "\n\n".join(paragraphs)
        note = _make_note(content)
        model = _mock_model()

        chunks = chunk_note(note, model, target_tokens=100, max_tokens=200)

        assert len(chunks) > 1
        # All text is preserved
        reconstructed = "\n\n".join(c.text for c in chunks)
        assert reconstructed == content.strip()
        # Chunk IDs follow the pattern
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == f"test-note-id__chunk_{i}"
            assert chunk.index == i

    def test_paragraph_boundary_splitting(self):
        """Chunks should split at paragraph boundaries (\\n\\n)."""
        para1 = "A" * 400  # 100 tokens
        para2 = "B" * 400  # 100 tokens
        para3 = "C" * 400  # 100 tokens
        content = f"{para1}\n\n{para2}\n\n{para3}"
        note = _make_note(content)
        model = _mock_model()

        # target=120 tokens: para1 alone fits, then para2, then para3
        chunks = chunk_note(note, model, target_tokens=120, max_tokens=200)

        assert len(chunks) == 3
        assert chunks[0].text == para1
        assert chunks[1].text == para2
        assert chunks[2].text == para3

    def test_sentence_splitting_for_oversized_paragraph(self):
        """A paragraph exceeding max_tokens is split on sentence boundaries."""
        # One huge paragraph with multiple sentences
        sentences = [f"Sentence number {i} with lots of content." for i in range(30)]
        content = " ".join(sentences)
        note = _make_note(content)
        model = _mock_model()

        # max_tokens=50 tokens → ~200 chars, the paragraph is much larger
        chunks = chunk_note(note, model, target_tokens=30, max_tokens=50)

        assert len(chunks) > 1
        # All chunks should have content
        for chunk in chunks:
            assert len(chunk.text) > 0

    def test_token_counting_uses_model(self):
        """Token counting delegates to the model's tokenize_count."""
        content = "Short note."
        note = _make_note(content)
        model = _mock_model()

        chunk_note(note, model, target_tokens=300)

        model.tokenize_count.assert_called()

    def test_chunk_id_format(self):
        """Chunk IDs follow {note_id}__chunk_{N} format."""
        content = "A" * 800 + "\n\n" + "B" * 800
        note = _make_note(content, note_id="abc-123")
        model = _mock_model()

        chunks = chunk_note(note, model, target_tokens=100, max_tokens=300)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == f"abc-123__chunk_{i}"
            assert chunk.note_id == "abc-123"

    def test_empty_content(self):
        """Empty content returns a single chunk with empty text."""
        note = _make_note("")
        model = _mock_model()

        chunks = chunk_note(note, model)

        assert len(chunks) == 1
        assert chunks[0].text == ""

    def test_merges_small_paragraphs(self):
        """Small consecutive paragraphs are merged up to target_tokens."""
        # Each paragraph is ~10 tokens at 4 chars/token
        small_paras = [f"Short {i}." for i in range(5)]
        # Plus a big paragraph to ensure the note exceeds target
        big_para = "X" * 1200  # 300 tokens
        content = "\n\n".join(small_paras) + "\n\n" + big_para
        note = _make_note(content)
        model = _mock_model()

        chunks = chunk_note(note, model, target_tokens=300, max_tokens=500)

        # The small paragraphs should be merged into the first chunk
        assert len(chunks) >= 2
        # First chunk should contain all small paragraphs merged
        for para in small_paras:
            assert para in chunks[0].text
