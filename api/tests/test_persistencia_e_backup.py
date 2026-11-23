"""Persistência local da biblioteca e backup criptografado (ADR 0024). Dados sintéticos."""

import pytest
from sqlalchemy import create_engine

from app.clients.sqlite_library_repository import SqliteLibraryRepository
from app.db.migrate import upgrade
from app.services import library_store
from app.services.backup_service import BackupError, export_backup, import_backup
from app.services.library_service import LIBRARY
from tests.helpers_api import cliente, enviar
from tests.test_transactions_api import OFX_SINTETICO

SENHA = "senha-de-teste-123"


@pytest.fixture
def banco(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'trokim.db'}"
    engine = create_engine(f"sqlite:///{tmp_path / 'trokim.db'}")
    with engine.begin() as conn:
        upgrade(conn, "app")
    engine.dispose()
    repo = SqliteLibraryRepository(url)
    yield repo
    repo.dispose()


async def _importar():
    async with cliente() as client:
        resposta = await enviar(client, OFX_SINTETICO, "extrato.ofx", owner="pessoal")
        assert resposta.status_code == 200


async def test_biblioteca_sobrevive_ao_reinicio(banco):
    library_store.configure(banco)
    await _importar()
    # o middleware gravou depois do upload; "reiniciar" é esvaziar a memória e restaurar
    antes = len(LIBRARY.transactions)
    assert antes == 2
    LIBRARY.reset()
    library_store.configure(banco)
    assert library_store.restore() is True
    assert len(LIBRARY.transactions) == antes
    assert next(iter(LIBRARY.accounts.values())).owner.value == "pessoal"
    assert LIBRARY.statements


async def test_grava_so_quando_a_biblioteca_mudou(banco):
    library_store.configure(banco)
    await _importar()
    assert library_store.persist() is False  # nada mudou desde o upload


async def test_restore_sem_nada_gravado_devolve_falso(banco):
    library_store.configure(banco)
    assert library_store.restore() is False


async def test_campos_privados_da_contraparte_sobrevivem(banco):
    from datetime import date

    from app.domain.models import Transaction, TransactionType

    LIBRARY.transactions.append(
        Transaction(
            account_id="x:1",
            description="PIX",
            amount=-10.0,
            date=date(2026, 11, 1),
            type=TransactionType.DEBIT,
            counterparty_doc="***.123.456-**",
            counterparty_account="0260:123",
        )
    )
    library_store.configure(banco)
    library_store.persist()
    LIBRARY.reset()
    library_store.restore()
    tx = LIBRARY.transactions[0]
    assert tx.counterparty_doc == "***.123.456-**"
    assert tx.counterparty_account == "0260:123"


async def test_backup_ida_e_volta_com_a_senha_certa():
    await _importar()
    snapshot = library_store.snapshot_from(LIBRARY)
    arquivo = export_backup(snapshot, SENHA)
    assert b"SUPERMERCADO" not in arquivo  # cifrado
    assert import_backup(arquivo, SENHA) == snapshot


def test_backup_com_senha_errada_ou_corrompido_falha():
    arquivo = export_backup(library_store.snapshot_from(LIBRARY), SENHA)
    with pytest.raises(BackupError, match="Senha incorreta"):
        import_backup(arquivo, "outra-senha-456")
    adulterado = arquivo[:-1] + bytes([arquivo[-1] ^ 1])
    with pytest.raises(BackupError):
        import_backup(adulterado, SENHA)
    with pytest.raises(BackupError, match="não é um backup"):
        import_backup(b"qualquer coisa", SENHA)


async def test_endpoint_exporta_e_restaura_substituindo():
    await _importar()
    async with cliente() as client:
        resposta = await client.post("/v1/backup/export", json={"passphrase": SENHA})
        assert resposta.status_code == 200
        assert ".trokim" in resposta.headers["content-disposition"]
        arquivo = resposta.content
        await client.delete("/v1/transactions/clear")
        assert LIBRARY.transactions == []
        resposta = await client.post(
            "/v1/backup/import",
            files={"file": ("b.trokim", arquivo)},
            data={"passphrase": SENHA, "mode": "substituir"},
        )
    assert resposta.status_code == 200
    assert resposta.json()["transactions_total"] == 2
    assert len(LIBRARY.transactions) == 2


async def test_mesclar_nao_duplica_lancamentos():
    await _importar()
    arquivo = export_backup(library_store.snapshot_from(LIBRARY), SENHA)
    async with cliente() as client:
        resposta = await client.post(
            "/v1/backup/import",
            files={"file": ("b.trokim", arquivo)},
            data={"passphrase": SENHA, "mode": "mesclar"},
        )
    assert resposta.status_code == 200
    assert resposta.json()["added"]["transactions"] == 0
    assert len(LIBRARY.transactions) == 2


async def test_endpoint_rejeita_senha_errada_e_senha_curta():
    await _importar()
    arquivo = export_backup(library_store.snapshot_from(LIBRARY), SENHA)
    async with cliente() as client:
        errada = await client.post(
            "/v1/backup/import",
            files={"file": ("b.trokim", arquivo)},
            data={"passphrase": "senha-errada-999"},
        )
        curta = await client.post("/v1/backup/export", json={"passphrase": "123"})
    assert errada.status_code == 400
    assert "Senha incorreta" in errada.json()["detail"]
    assert curta.status_code == 422
