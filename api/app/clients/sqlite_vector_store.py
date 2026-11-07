"""Banco vetorial persistente em SQLite com a extensão sqlite-vec.

Escolha coerente com a ADR 0002 (SQLite local-first) e mais leve que ChromaDB.
A busca usa distância de cosseno; como os vetores são normalizados, a
similaridade devolvida é 1 - distância (equivalente ao produto interno).
"""

import sqlite3
from pathlib import Path

import sqlite_vec

from app.domain.models import EvidenceChunk


class SQLiteVectorStore:
    """Implementa a port VectorStore com sqlite-vec (tabela virtual vec0)."""

    def __init__(self, path: str | Path, dimension: int = 384):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.dimension = dimension
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        existing = self.get_meta("embedding_dimension")
        if existing is not None and int(existing) != self.dimension:
            self._conn.execute("DROP TABLE IF EXISTS vec_chunks")
            self._conn.execute("DROP TABLE IF EXISTS chunks")
            self._conn.execute("DELETE FROM meta WHERE key != 'embedding_dimension'")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id TEXT NOT NULL UNIQUE,
                document_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT,
                document_title TEXT NOT NULL,
                section TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                embedding float[{self.dimension}] distance_metric=cosine
            )
            """
        )
        self.set_meta("embedding_dimension", str(self.dimension))
        self._conn.commit()

    def _row_to_chunk(self, row: tuple) -> EvidenceChunk:
        return EvidenceChunk(
            id=row[1],
            document_id=row[2],
            source_name=row[3],
            source_url=row[4],
            document_title=row[5],
            section=row[6],
            content=row[7],
        )

    def reset(self) -> None:
        self._conn.execute("DELETE FROM vec_chunks")
        self._conn.execute("DELETE FROM chunks")
        self._conn.execute("DELETE FROM meta WHERE key != 'embedding_dimension'")
        self._conn.commit()

    def add(self, chunks: list[EvidenceChunk], vectors: list[list[float]]) -> None:
        for chunk, vector in zip(chunks, vectors, strict=True):
            cursor = self._conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, document_id, source_name, source_url,
                    document_title, section, content
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    chunk.document_id,
                    chunk.source_name,
                    chunk.source_url,
                    chunk.document_title,
                    chunk.section,
                    chunk.content,
                ),
            )
            self._conn.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (cursor.lastrowid, sqlite_vec.serialize_float32(vector)),
            )
        self._conn.commit()

    def search(self, vector: list[float], k: int) -> list[tuple[EvidenceChunk, float]]:
        rows = self._conn.execute(
            """
            SELECT c.*, v.distance
            FROM vec_chunks v
            JOIN chunks c ON c.rowid = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
            """,
            (sqlite_vec.serialize_float32(vector), k),
        ).fetchall()
        return [(self._row_to_chunk(row), 1.0 - row[8]) for row in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def all(self) -> list[EvidenceChunk]:
        rows = self._conn.execute("SELECT * FROM chunks ORDER BY rowid").fetchall()
        return [self._row_to_chunk(row) for row in rows]

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()
