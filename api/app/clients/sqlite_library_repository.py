"""Adaptador SQLite da porta ``LibraryRepository`` (tabela ``library_snapshot``, migração 002)."""

from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.domain.snapshot import SNAPSHOT_VERSION, LibrarySnapshot
from app.models.library_repository import LibraryRepository


def sync_url(database_url: str) -> str:
    """Converte a URL assíncrona da aplicação (``sqlite+aiosqlite``) na síncrona."""
    return database_url.replace("sqlite+aiosqlite", "sqlite", 1)


class SqliteLibraryRepository(LibraryRepository):
    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(sync_url(database_url))

    def load(self) -> LibrarySnapshot | None:
        with self._engine.connect() as conn:
            row = conn.execute(text("SELECT payload FROM library_snapshot WHERE id = 1")).first()
        if row is None:
            return None
        return LibrarySnapshot.model_validate_json(row[0])

    def save(self, snapshot: LibrarySnapshot) -> None:
        payload = snapshot.model_dump_json()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO library_snapshot (id, version, payload, updated_at) "
                    "VALUES (1, :version, :payload, :updated_at) "
                    "ON CONFLICT(id) DO UPDATE SET version = excluded.version, "
                    "payload = excluded.payload, updated_at = excluded.updated_at"
                ),
                {
                    "version": SNAPSHOT_VERSION,
                    "payload": payload,
                    "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                },
            )

    def dispose(self) -> None:
        self._engine.dispose()
