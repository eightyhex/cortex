"""LanceDB-based vector store for semantic search."""

from __future__ import annotations

from pathlib import Path

import lancedb
import pyarrow as pa

from cortex.index.chunker import Chunk, chunk_note
from cortex.index.lexical import SearchResult
from cortex.index.models import EmbeddingModel
from cortex.vault.parser import Note


class SemanticIndex:
    """Vector search index backed by LanceDB.

    Stores note chunks with their embeddings and supports cosine similarity search.
    """

    TABLE_NAME = "chunks"

    _schema = pa.schema([
        pa.field("id", pa.utf8()),
        pa.field("note_id", pa.utf8()),
        pa.field("title", pa.utf8()),
        pa.field("note_type", pa.utf8()),
        pa.field("text", pa.utf8()),
        pa.field("vector", pa.list_(pa.float32(), 768)),
        pa.field("tags", pa.utf8()),
        pa.field("created", pa.utf8()),
    ])

    def __init__(self, db_path: Path, model: EmbeddingModel) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(db_path))
        self._model = model
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the chunks table if it doesn't exist."""
        if self.TABLE_NAME not in self._db.list_tables():
            self._db.create_table(self.TABLE_NAME, schema=self._schema)

    def _get_table(self):
        return self._db.open_table(self.TABLE_NAME)

    def index_note(self, note: Note) -> None:
        """Chunk the note, embed chunks, and store in LanceDB."""
        # Remove existing chunks for this note first
        self.remove_note(note.id)

        chunks = chunk_note(note, self._model)
        if not chunks:
            return

        texts = [c.text for c in chunks]
        vectors = self._model.embed_batch(texts)

        tags_str = ",".join(note.tags)
        created_str = note.created if isinstance(note.created, str) else (
            note.created.isoformat() if note.created else ""
        )

        records = []
        for chunk, vector in zip(chunks, vectors):
            records.append({
                "id": chunk.chunk_id,
                "note_id": note.id,
                "title": note.title,
                "note_type": note.note_type,
                "text": chunk.text,
                "vector": vector,
                "tags": tags_str,
                "created": created_str,
            })

        table = self._get_table()
        table.add(records)

    def remove_note(self, note_id: str) -> None:
        """Delete all chunks for a note."""
        table = self._get_table()
        try:
            table.delete(f"note_id = '{note_id}'")
        except Exception:
            # Table may be empty or note not found — ignore
            pass

    def rebuild(self, notes: list[Note]) -> None:
        """Clear and rebuild the index from scratch."""
        # Drop and recreate the table
        try:
            self._db.drop_table(self.TABLE_NAME)
        except Exception:
            pass
        self._db.create_table(self.TABLE_NAME, schema=self._schema)

        for note in notes:
            self.index_note(note)

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        """Embed query and perform cosine similarity search."""
        query_vector = self._model.embed(query)

        table = self._get_table()

        # Check if table has data
        if table.count_rows() == 0:
            return []

        results_raw = (
            table.search(query_vector)
            .metric("cosine")
            .limit(limit)
            .to_list()
        )

        # Deduplicate by note_id — keep highest scoring chunk per note
        seen: dict[str, SearchResult] = {}
        for row in results_raw:
            note_id = row["note_id"]
            # LanceDB cosine distance: lower = more similar.
            # Convert to a similarity score (1 - distance).
            score = 1.0 - row["_distance"]
            if note_id not in seen or score > seen[note_id].score:
                seen[note_id] = SearchResult(
                    note_id=note_id,
                    title=row["title"],
                    score=score,
                    snippet=row["text"][:200],
                    note_type=row["note_type"],
                    path="",
                )

        return sorted(seen.values(), key=lambda r: r.score, reverse=True)
