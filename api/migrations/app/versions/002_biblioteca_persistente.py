"""Biblioteca persistente: um retrato versionado da biblioteca do usuário.

Revisão: 002
Anterior: 001

Uma linha (``id = 1``) guarda o retrato inteiro em JSON, o mesmo formato do backup. A decisão e
o caminho para tabelas normalizadas estão na ADR 0024.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("library_snapshot")
