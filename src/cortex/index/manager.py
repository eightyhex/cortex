"""IndexManager — orchestrates search indexes (lexical + semantic)."""

from __future__ import annotations

from cortex.config import CortexConfig
from cortex.index.lexical import LexicalIndex
from cortex.index.models import EmbeddingModel
from cortex.index.semantic import SemanticIndex
from cortex.vault.parser import Note


class IndexManager:
    """Orchestrates all search indexes (lexical and semantic)."""

    def __init__(self, config: CortexConfig) -> None:
        data_dir = config.vault.path.parent / "data"
        self._lexical = LexicalIndex(data_dir / "lexical.duckdb")
        model = EmbeddingModel()
        self._semantic = SemanticIndex(data_dir / "semantic.lancedb", model)

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

    def remove_note(self, note_id: str) -> None:
        """Remove a note from all search indexes."""
        self._lexical.remove_note(note_id)
        self._semantic.remove_note(note_id)

    def reindex_note(self, note: Note) -> None:
        """Re-index a note (remove + add) in all search indexes."""
        self._lexical.remove_note(note.id)
        self._lexical.index_note(note)
        self._semantic.remove_note(note.id)
        self._semantic.index_note(note)

    def rebuild_all(self, notes: list[Note]) -> None:
        """Full rebuild of all search indexes."""
        self._lexical.rebuild(notes)
        self._semantic.rebuild(notes)

    def close(self) -> None:
        """Close all index connections."""
        self._lexical.close()
