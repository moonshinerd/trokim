"""Aplica as migrações Alembic dos bancos SQLite do Trokim (ADR 0019).

Cada banco tem a sua pasta em ``api/migrations/<nome>/`` e revisões numeradas em sequência
(``001_esquema_inicial.py``, ``002_...``). Ao abrir o banco, o código chama :func:`upgrade`, que
aplica só o que falta até a última revisão (``head``).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def upgrade(connection: Connection, name: str, **attributes: object) -> None:
    """Leva o banco da conexão até a última revisão da pasta ``migrations/<name>``."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS / name))
    config.attributes["connection"] = connection
    config.attributes.update(attributes)
    command.upgrade(config, "head")


def current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()
