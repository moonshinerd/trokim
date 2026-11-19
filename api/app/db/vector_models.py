"""Modelos ORM da base vetorial do RAG (ADR 0007), migrados por ``migrations/vetorial``.

A tabela virtual ``vec_chunks`` (sqlite-vec) não tem modelo: o ORM não representa tabelas
``vec0`` nem o operador ``MATCH``. Ela é criada na migração e consultada no adaptador.
"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class VectorBase(DeclarativeBase):
    pass


class MetaEntry(VectorBase):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class ChunkRow(VectorBase):
    __tablename__ = "chunks"
    __table_args__ = {"sqlite_autoincrement": True}

    rowid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String, unique=True)
    document_id: Mapped[str] = mapped_column(String)
    source_name: Mapped[str] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    document_title: Mapped[str] = mapped_column(String)
    section: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
