"""IndexManager — orchestrates search indexes (lexical + semantic)."""

from __future__ import annotations

import hashlib

from cortex.config import CortexConfig
from cortex.index.lexical import LexicalIndex
from cortex.index.models import EmbeddingModel
from cortex.index.semantic import SemanticIndex
from cortex.vault.parser import Note


def _note_content_hash(note: Note) -> str:
    """Compute a hash of note content + key metadata for change detection."""
    parts = [
        note.content,
        note.title,
        note.status,
        ",".join(sorted(note.tags)),
        str(note.modified),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class IndexManager:
    """Orchestrates all search indexes (lexical and semantic)."""

    def __init__(self, config: CortexConfig) -> None:
        data_dir = config.vault.path.parent / "data"
        self._lexical = LexicalIndex(data_dir / "lexical.duckdb")
        model = EmbeddingModel()
        self._semantic = SemanticIndex(data_dir / "semantic.lancedb", model)
        self._content_hashes: dict[str, str] = {}

    @property
    def lexical(self) -> LexicalIndex:
        return self._lexical

    @property
    def semantic(self) -> SemanticIndex:
        return self._semantic

    def index_note(self, note: Note) -> None:
        """Index a note in all search indexes."""
        self._lexical.index_note(note)
        self._semantic.index_note(note)
        self._content_hashes[note.id] = _note_content_hash(note)

    def remove_note(self, note_id: str) -> None:
        """Remove a note from all search indexes."""
        self._lexical.remove_note(note_id)
        self._semantic.remove_note(note_id)
        self._content_hashes.pop(note_id, None)

    def reindex_note(self, note: Note) -> None:
        """Re-index a note (remove + add) in all search indexes.

        No-op if the note content hasn't changed since last indexing.
        """
        new_hash = _note_content_hash(note)
        if self._content_hashes.get(note.id) == new_hash:
            return  # Content unchanged — skip reindex
        self._lexical.remove_note(note.id)
        self._lexical.index_note(note)
        self._semantic.remove_note(note.id)
        self._semantic.index_note(note)
        self._content_hashes[note.id] = new_hash

    def rebuild_all(self, notes: list[Note]) -> None:
        """Full rebuild of all search indexes."""
        self._lexical.rebuild(notes)
        self._semantic.rebuild(notes)

    def close(self) -> None:
        """Close all index connections."""
        self._lexical.close()
