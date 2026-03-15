"""Semantic boundary chunker — splits notes into chunks at paragraph/sentence boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass

from cortex.index.models import EmbeddingModel
from cortex.vault.parser import Note

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    """A chunk of text from a note."""

    chunk_id: str
    note_id: str
    text: str
    index: int


def chunk_note(
    note: Note,
    model: EmbeddingModel,
    target_tokens: int = 300,
    max_tokens: int = 500,
) -> list[Chunk]:
    """Split a note into chunks at semantic boundaries.

    Strategy:
    1. Split on paragraph boundaries (\\n\\n) first.
    2. If a paragraph exceeds max_tokens, split on sentence boundaries.
    3. Merge small consecutive paragraphs to approach target_tokens.
    4. Short notes (< target_tokens) become a single chunk.
    """
    text = note.content.strip()
    if not text:
        return [Chunk(
            chunk_id=f"{note.id}__chunk_0",
            note_id=note.id,
            text="",
            index=0,
        )]

    # If the whole note fits in target, return as single chunk
    total_tokens = model.tokenize_count(text)
    if total_tokens <= target_tokens:
        return [Chunk(
            chunk_id=f"{note.id}__chunk_0",
            note_id=note.id,
            text=text,
            index=0,
        )]

    # Split into paragraphs
    paragraphs = re.split(r"\n\n+", text)

    # Break oversized paragraphs into sentences
    segments: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if model.tokenize_count(para) <= max_tokens:
            segments.append(para)
        else:
            # Split on sentence boundaries
            sentences = _SENTENCE_RE.split(para)
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence:
                    segments.append(sentence)

    # Merge small segments to approach target_tokens
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_tokens = 0

    for segment in segments:
        seg_tokens = model.tokenize_count(segment)

        if current_parts and current_tokens + seg_tokens > target_tokens:
            # Flush current accumulator
            chunks.append(Chunk(
                chunk_id=f"{note.id}__chunk_{len(chunks)}",
                note_id=note.id,
                text="\n\n".join(current_parts),
                index=len(chunks),
            ))
            current_parts = [segment]
            current_tokens = seg_tokens
        else:
            current_parts.append(segment)
            current_tokens += seg_tokens

    # Flush remaining
    if current_parts:
        chunks.append(Chunk(
            chunk_id=f"{note.id}__chunk_{len(chunks)}",
            note_id=note.id,
            text="\n\n".join(current_parts),
            index=len(chunks),
        ))

    return chunks
