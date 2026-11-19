"""Migrações Alembic numeradas dos bancos SQLite (ADR 0019)."""

import ast
import asyncio
import re
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.db.migrate import MIGRATIONS, current_revision, upgrade

BANCOS = ["app", "vetorial"]


def _revisoes(nome: str) -> list[tuple[str, str, str | None]]:
    """(arquivo, revision, down_revision) de cada revisão, lidos sem importar o módulo."""
    saida = []
    for path in sorted((MIGRATIONS / nome / "versions").glob("*.py")):
        valores = {}
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                valores[node.target.id] = ast.literal_eval(node.value)
        saida.append((path.name, valores["revision"], valores["down_revision"]))
    return saida


@pytest.mark.parametrize("nome", BANCOS)
def test_revisoes_numeradas_em_sequencia(nome):
    revisoes = _revisoes(nome)
    assert revisoes, f"migrations/{nome} sem revisões"
    for posicao, (arquivo, revision, down) in enumerate(revisoes, 1):
        assert re.fullmatch(r"\d{3}_[a-z0-9_]+\.py", arquivo), arquivo
        assert revision == f"{posicao:03d}" == arquivo[:3], arquivo
        assert down == (None if posicao == 1 else f"{posicao - 1:03d}"), arquivo


def _ultima(nome: str) -> str:
    return _revisoes(nome)[-1][1]


def test_banco_da_aplicacao_novo_chega_na_ultima_revisao(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    with engine.begin() as conn:
        upgrade(conn, "app")
        upgrade(conn, "app")  # reaplicar não faz nada
        assert current_revision(conn) == _ultima("app")
        assert inspect(conn).has_table("transactions")


def test_banco_da_aplicacao_criado_com_create_all_e_adotado(tmp_path):
    from app.db.database import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'legado.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO transactions (account_id, description, amount, transaction_date, "
                "transaction_type, category) "
                "VALUES ('a', 'x', 1.0, '2026-11-18', 'debit', 'outros')"
            )
        )
        upgrade(conn, "app")
        assert current_revision(conn) == _ultima("app")
        assert conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar() == 1


def test_init_db_usa_as_migracoes(tmp_path, monkeypatch):
    from app.db import database

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'init.db'}")
    monkeypatch.setattr(database, "engine", engine)
    asyncio.run(database.init_db())
    asyncio.run(engine.dispose())
    conn = sqlite3.connect(tmp_path / "init.db")
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == _ultima("app")


def test_banco_vetorial_novo_fica_na_ultima_revisao(tmp_path):
    store = SQLiteVectorStore(tmp_path / "v.db", dimension=2)
    with store.engine.connect() as conn:
        assert current_revision(conn) == _ultima("vetorial")


def test_banco_vetorial_anterior_as_migracoes_e_adotado_sem_perder_dados(tmp_path):
    """Bancos criados antes da ADR 0019 (sem alembic_version) viram 001 sem reindexar."""
    path = tmp_path / "legado.db"
    store = SQLiteVectorStore(path, dimension=2)
    with store.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO chunks (chunk_id, document_id, source_name, document_title, "
                "section, content) VALUES ('c1', 'd1', 'BCB', 'Doc', 'S', 'texto')"
            )
        )
        conn.execute(text("DROP TABLE alembic_version"))
    reaberto = SQLiteVectorStore(path, dimension=2)
    assert reaberto.count() == 1
    with reaberto.engine.connect() as conn:
        assert current_revision(conn) == _ultima("vetorial")


def test_trocar_a_dimensao_recria_o_indice_na_ultima_revisao(tmp_path):
    path = tmp_path / "dim.db"
    SQLiteVectorStore(path, dimension=2).set_meta("fingerprint", "x")
    store = SQLiteVectorStore(path, dimension=3)
    assert store.get_meta("embedding_dimension") == "3"
    assert store.get_meta("fingerprint") is None
    with store.engine.connect() as conn:
        assert current_revision(conn) == _ultima("vetorial")


def test_alembic_ini_aponta_para_as_pastas_de_migracao():
    ini = (Path(__file__).resolve().parents[1] / "alembic.ini").read_text(encoding="utf-8")
    for nome in BANCOS:
        assert f"[{nome}]" in ini
        assert f"%(here)s/migrations/{nome}" in ini
