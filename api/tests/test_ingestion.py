from pathlib import Path

import pytest
from test_rag import FakeEmbedder

from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.core.config import settings
from app.services.ingestion_service import ingest
from app.services.rag_service import RAGService

BASE = Path(__file__).resolve().parents[2] / "research" / "knowledge_base"


def test_ingestao_da_base_real_e_idempotencia(tmp_path):
    store = SQLiteVectorStore(tmp_path / "corpus.db", dimension=2)
    embedder = FakeEmbedder()
    report = ingest(BASE, store, embedder)
    assert report is not None
    assert store.count() >= 20
    results = store.search([1.0, 0.0], store.count())
    assert {chunk.document_id for chunk, _ in results} == {path.name for path in BASE.glob("*.txt")}
    assert len({chunk.document_id for chunk, _ in results}) == 20
    assert all(
        "FONTE:" not in chunk.content and "URL:" not in chunk.content for chunk, _ in results
    )
    assert all(chunk.section != "Introdução" for chunk, _ in results)
    assert all(len(chunk.content) <= settings.RAG_CHUNK_MAX_CHARS for chunk, _ in results)
    assert report.documents_read == 20
    assert report.chunks_generated == store.count()
    assert report.dimension == 2
    assert report.model == embedder.name
    assert report.reingested is True
    calls = embedder.calls
    count = store.count()
    second = ingest(BASE, store, embedder)
    assert second.reingested is False
    assert second.corpus_hash == report.corpus_hash
    assert embedder.calls == calls
    assert store.count() == count


@pytest.mark.parametrize("change", ["corpus", "modelo", "max_chars", "overlap"])
def test_mudanca_de_corpus_modelo_ou_config_reingere(tmp_path, monkeypatch, change):
    base = tmp_path / "base"
    base.mkdir()
    document = base / "teste.txt"
    document.write_text(
        "FONTE: Banco Central do Brasil\nTITULO: Planejamento\n"
        "URL: https://www.bcb.gov.br/\n[SEÇÃO 1: Reserva]\n"
        + "Planeje uma reserva financeira. "
        * 30,
        encoding="utf-8",
    )
    store = SQLiteVectorStore(tmp_path / "changed.db", dimension=2)
    embedder = FakeEmbedder()
    RAGService(str(base), store=store, embedder=embedder)
    calls = embedder.calls
    RAGService(str(base), store=store, embedder=embedder)
    assert embedder.calls == calls
    if change == "corpus":
        document.write_text(
            document.read_text(encoding="utf-8") + "Considere imprevistos.", encoding="utf-8"
        )
    elif change == "modelo":
        embedder.name = "outro-modelo-deterministico"
    elif change == "max_chars":
        monkeypatch.setattr(settings, "RAG_CHUNK_MAX_CHARS", 200)
    else:
        monkeypatch.setattr(settings, "RAG_CHUNK_OVERLAP_TOKENS", 0)
    RAGService(str(base), store=store, embedder=embedder)
    assert embedder.calls > calls
    calls = embedder.calls
    RAGService(str(base), store=store, embedder=embedder)
    assert embedder.calls == calls
