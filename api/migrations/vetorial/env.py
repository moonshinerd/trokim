"""Ambiente Alembic da base vetorial do RAG (sqlite-vec)."""

from alembic import context

from app.clients.sqlite_vector_store import create_vector_engine
from app.db.vector_models import VectorBase

config = context.config


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    # A tabela virtual vec0 e as tabelas internas dela não são do ORM.
    return not (type_ == "table" and name.startswith("vec_chunks"))


def run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=VectorBase.metadata,
        render_as_batch=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:  # chamado pelo SQLiteVectorStore
    run(connection)
else:  # chamado pela linha de comando do Alembic
    url = config.get_main_option("sqlalchemy.url").removeprefix("sqlite:///")
    with create_vector_engine(url).begin() as conn:
        run(conn)
