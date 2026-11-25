from sqlalchemy import create_engine

from app.clients.sqlite_library_repository import SqliteLibraryRepository
from app.db.migrate import upgrade
from app.domain.models import TransactionOrigin
from app.services import library_store
from app.services.library_service import LIBRARY


async def test_origem_e_tipo_financeiro_sobrevivem_ao_sqlite(client, invoice, tmp_path):
    path = tmp_path / "library.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        upgrade(connection, "app")
    engine.dispose()
    repository = SqliteLibraryRepository(f"sqlite+aiosqlite:///{path}")
    library_store.configure(repository)
    try:
        first = await client.post("/v1/documents/confirm", json=invoice)
        assert first.status_code == 200
        LIBRARY.reset()
        assert library_store.restore()
        assert len(LIBRARY.transactions) == 2
        assert all(tx.origin == TransactionOrigin.DOCUMENT for tx in LIBRARY.transactions)
        assert all(tx.source_kind == "cartao" for tx in LIBRARY.transactions)
        assert [tx.uid for tx in LIBRARY.transactions] == first.json()["uids"]
        again = await client.post("/v1/documents/confirm", json=invoice)
        assert again.json()["outcome"] == "repetido"
    finally:
        library_store.configure(None)
        repository.dispose()
