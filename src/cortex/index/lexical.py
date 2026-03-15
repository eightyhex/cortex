"""DuckDB-based full-text search index with BM25 scoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from cortex.vault.parser import Note


@dataclass
class SearchResult:
    """A single search result from the lexical index."""

    note_id: str
    title: str
    score: float
    snippet: str
    note_type: str
    path: str


class LexicalIndex:
    """Full-text search index backed by DuckDB.

    Stores structured note metadata and provides BM25-scored full-text search
    with optional filters on note_type, tags, status, and date_range.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the notes table if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                note_type VARCHAR,
                path VARCHAR,
                content TEXT,
                tags VARCHAR[],
                tags_text VARCHAR,
                status VARCHAR,
                source_url VARCHAR,
                created TIMESTAMP,
                modified TIMESTAMP,
                supersedes VARCHAR,
                superseded_by VARCHAR,
                archived_date TIMESTAMP
            )
        """)

    def _create_fts_index(self) -> None:
        """Create the FTS index on the notes table."""
        # Drop existing FTS index if present
        try:
            self._conn.execute("PRAGMA drop_fts_index('notes')")
        except duckdb.CatalogException:
            pass
        self._conn.execute(
            "PRAGMA create_fts_index('notes', 'id', 'title', 'content', 'tags_text')"
        )

    def index_note(self, note: Note) -> None:
        """Upsert a note into the index."""
        tags_text = " ".join(note.tags)
        source_url = note.frontmatter.get("source_url", "")

        # DELETE + INSERT for upsert (DuckDB doesn't have native UPSERT for all cases)
        self._conn.execute("DELETE FROM notes WHERE id = ?", [note.id])
        self._conn.execute(
            """
            INSERT INTO notes (id, title, note_type, path, content, tags, tags_text,
                               status, source_url, created, modified,
                               supersedes, superseded_by, archived_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                note.id,
                note.title,
                note.note_type,
                str(note.path),
                note.content,
                note.tags,
                tags_text,
                note.status,
                source_url,
                note.created,
                note.modified,
                note.supersedes,
                note.superseded_by,
                note.archived_date,
            ],
        )
        # Rebuild FTS index after modification
        self._create_fts_index()

    def remove_note(self, note_id: str) -> None:
        """Remove a note from the index."""
        self._conn.execute("DELETE FROM notes WHERE id = ?", [note_id])
        self._create_fts_index()

    def rebuild(self, notes: list[Note]) -> None:
        """Drop and recreate the table, insert all notes, and build FTS index."""
        self._conn.execute("DROP TABLE IF EXISTS notes")
        self._ensure_table()

        for note in notes:
            tags_text = " ".join(note.tags)
            source_url = note.frontmatter.get("source_url", "")
            self._conn.execute(
                """
                INSERT INTO notes (id, title, note_type, path, content, tags, tags_text,
                                   status, source_url, created, modified,
                                   supersedes, superseded_by, archived_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    note.id,
                    note.title,
                    note.note_type,
                    str(note.path),
                    note.content,
                    note.tags,
                    tags_text,
                    note.status,
                    source_url,
                    note.created,
                    note.modified,
                    note.supersedes,
                    note.superseded_by,
                    note.archived_date,
                ],
            )

        self._create_fts_index()

    def search(
        self,
        query: str,
        limit: int = 20,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """BM25 full-text search with optional filters.

        Filters:
            note_type: str — filter by note type
            tags: list[str] — filter by tags (note must have ALL specified tags)
            status: str — filter by status
            date_range: tuple[datetime, datetime] — filter by created date range
        """
        filters = filters or {}

        # Build the FTS match query
        sql = """
            SELECT n.id, n.title, fts.score, n.content, n.note_type, n.path
            FROM notes n
            JOIN (
                SELECT *, fts_main_notes.match_bm25(id, ?) AS score
                FROM notes
            ) fts ON n.id = fts.id
            WHERE fts.score IS NOT NULL
        """
        params: list = [query]

        if "note_type" in filters:
            sql += " AND n.note_type = ?"
            params.append(filters["note_type"])

        if "status" in filters:
            sql += " AND n.status = ?"
            params.append(filters["status"])

        if "tags" in filters:
            for tag in filters["tags"]:
                sql += " AND list_contains(n.tags, ?)"
                params.append(tag)

        if "date_range" in filters:
            start, end = filters["date_range"]
            sql += " AND n.created >= ? AND n.created <= ?"
            params.append(start)
            params.append(end)

        sql += " ORDER BY fts.score DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            note_id, title, score, content, note_type, path = row
            # Generate a snippet (first 200 chars of content)
            snippet = content[:200].strip() if content else ""
            results.append(
                SearchResult(
                    note_id=note_id,
                    title=title,
                    score=score,
                    snippet=snippet,
                    note_type=note_type,
                    path=path,
                )
            )

        return results

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
