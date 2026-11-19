"""Banco vetorial persistente em SQLite com a extensão sqlite-vec.

Escolha coerente com a ADR 0002 (SQLite local-first) e mais leve que ChromaDB.
A busca usa distância de cosseno; como os vetores são normalizados, a
similaridade devolvida é 1 - distância (equivalente ao produto interno).

Metadados e trechos usam o ORM (``app.db.vector_models``) e o esquema vem das migrações
numeradas em ``migrations/vetorial`` (ADR 0019). Só a tabela virtual ``vec_chunks`` é acessada
por SQL textual, porque o ORM não representa ``vec0`` nem o operador ``MATCH``.
"""

from pathlib import Path

import sqlite_vec
from sqlalchemy import Engine, create_engine, delete, event, func, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.db.migrate import upgrade
from app.db.vector_models import ChunkRow, MetaEntry
from app.domain.models import EvidenceChunk


def create_vector_engine(path: str | Path) -> Engine:
    """Engine SQLite que carrega a extensão sqlite-vec em cada conexão."""
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _load_sqlite_vec(dbapi_connection, _record) -> None:
        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)
        dbapi_connection.enable_load_extension(False)

    return engine


class SQLiteVectorStore:
    """Implementa a port VectorStore com sqlite-vec (tabela virtual vec0)."""

    def __init__(self, path: str | Path, dimension: int = 384):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.dimension = dimension
        self.engine = create_vector_engine(self.path)
        self._session = sessionmaker(self.engine, expire_on_commit=False)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Aplica as migrações; trocar a dimensão dos embeddings recria o índice."""
        with self.engine.begin() as conn:
            existing = None
            if inspect(conn).has_table("meta"):
                existing = conn.execute(
                    select(MetaEntry.value).where(MetaEntry.key == "embedding_dimension")
                ).scalar()
            if existing is not None and int(existing) != self.dimension:
                # Os vetores derivam dos documentos: com outro modelo de embeddings, o índice é
                # refeito do zero (a reindexação roda em `make ingest`).
                for table in ("vec_chunks", "chunks", "meta", "alembic_version"):
                    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            upgrade(conn, "vetorial", embedding_dimension=int(self.dimension))
        self.set_meta("embedding_dimension", str(self.dimension))

    @staticmethod
    def _to_chunk(row: ChunkRow) -> EvidenceChunk:
        return EvidenceChunk(
            id=row.chunk_id,
            document_id=row.document_id,
            source_name=row.source_name,
            source_url=row.source_url,
            document_title=row.document_title,
            section=row.section,
            content=row.content,
        )

    def reset(self) -> None:
        with self._session.begin() as session:
            session.execute(text("DELETE FROM vec_chunks"))
            session.execute(delete(ChunkRow))
            session.execute(delete(MetaEntry).where(MetaEntry.key != "embedding_dimension"))

    def add(self, chunks: list[EvidenceChunk], vectors: list[list[float]]) -> None:
        with self._session.begin() as session:
            for chunk, vector in zip(chunks, vectors, strict=True):
                row = ChunkRow(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    source_name=chunk.source_name,
                    source_url=chunk.source_url,
                    document_title=chunk.document_title,
                    section=chunk.section,
                    content=chunk.content,
                )
                session.add(row)
                session.flush()  # gera o rowid que liga o trecho ao vetor
                session.execute(
                    text("INSERT INTO vec_chunks (rowid, embedding) VALUES (:rowid, :embedding)"),
                    {"rowid": row.rowid, "embedding": sqlite_vec.serialize_float32(vector)},
                )

    def search(self, vector: list[float], k: int) -> list[tuple[EvidenceChunk, float]]:
        with self._session() as session:
            nearest = session.execute(
                text(
                    "SELECT rowid, distance FROM vec_chunks "
                    "WHERE embedding MATCH :embedding AND k = :k ORDER BY distance"
                ),
                {"embedding": sqlite_vec.serialize_float32(vector), "k": k},
            ).all()
            if not nearest:
                return []
            rows = {
                row.rowid: row
                for row in session.scalars(
                    select(ChunkRow).where(ChunkRow.rowid.in_([r.rowid for r in nearest]))
                )
            }
        return [(self._to_chunk(rows[r.rowid]), 1.0 - r.distance) for r in nearest]

    def count(self) -> int:
        with self._session() as session:
            return session.scalar(select(func.count()).select_from(ChunkRow)) or 0

    def all(self) -> list[EvidenceChunk]:
        with self._session() as session:
            return [
                self._to_chunk(row)
                for row in session.scalars(select(ChunkRow).order_by(ChunkRow.rowid))
            ]

    def get_meta(self, key: str) -> str | None:
        with self._session() as session:
            entry = session.get(MetaEntry, key)
            return entry.value if entry else None

    def set_meta(self, key: str, value: str) -> None:
        with self._session.begin() as session:
            session.merge(MetaEntry(key=key, value=value))
