"""Ambiente Alembic do banco da aplicação (``DATABASE_URL``)."""

from alembic import context
from sqlalchemy import create_engine

from app.db.database import Base

config = context.config


def run(connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:  # chamado pela API (app.db.migrate.upgrade)
    run(connection)
else:  # chamado pela linha de comando do Alembic
    with create_engine(config.get_main_option("sqlalchemy.url")).begin() as conn:
        run(conn)
