"""IndexManager — orchestrates search indexes (lexical, and later semantic)."""

from __future__ import annotations

from cortex.config import CortexConfig
from cortex.index.lexical import LexicalIndex
from cortex.vault.parser import Note


class IndexManager:
    """Orchestrates all search indexes.

    Currently delegates to LexicalIndex. SemanticIndex will be added in a future task.
    """

    def __init__(self, config: CortexConfig) -> None:
        data_dir = config.vault.path.parent / "data"
        db_path = data_dir / "lexical.duckdb"
        self._lexical = LexicalIndex(db_path)

    @property
    def lexical(self) -> LexicalIndex:
        return self._lexical

    def index_note(self, note: Note) -> None:
        """Index a note in all search indexes."""
        self._lexical.index_note(note)

    def remove_note(self, note_id: str) -> None:
        """Remove a note from all search indexes."""
        self._lexical.remove_note(note_id)

    def reindex_note(self, note: Note) -> None:
        """Re-index a note (remove + add) in all search indexes."""
        self._lexical.remove_note(note.id)
        self._lexical.index_note(note)

    def rebuild_all(self, notes: list[Note]) -> None:
        """Full rebuild of all search indexes."""
        self._lexical.rebuild(notes)

    def close(self) -> None:
        """Close all index connections."""
        self._lexical.close()
