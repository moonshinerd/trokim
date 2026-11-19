"""Esquema inicial da base vetorial: metadados, trechos e índice sqlite-vec.

Revisão: 001
Anterior: nenhuma

``if_not_exists`` adota os bancos criados antes das migrações. A dimensão dos embeddings vem
do ``SQLiteVectorStore`` (atributo ``embedding_dimension``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meta",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "chunks",
        sa.Column("rowid", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chunk_id", sa.String(), nullable=False, unique=True),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("document_title", sa.String(), nullable=False),
        sa.Column("section", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
        if_not_exists=True,
    )
    dimension = int(context.config.attributes.get("embedding_dimension", 384))
    # Tabela virtual do sqlite-vec: sem equivalente no ORM, por isso em DDL.
    op.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0("
        f"embedding float[{dimension}] distance_metric=cosine)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vec_chunks")
    op.drop_table("chunks")
    op.drop_table("meta")
