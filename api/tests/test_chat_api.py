import pytest
from fastapi.testclient import TestClient
from test_rag import FakeEmbedder

from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.core.config import settings
from app.main import app
from app.routers.v1.chat import get_rag_service
from app.services.rag_service import RAGService


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RAG_HYBRID_ALPHA", 0.0)
    service = RAGService(
        embedder=FakeEmbedder(),
        store=SQLiteVectorStore(tmp_path / "chat.db", dimension=2),
    )
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_rag_service] = lambda: service
    client = TestClient(app)
    try:
        yield client, service
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_pergunta_valida_retorna_evidencia_oficial(client):
    http, _ = client
    message = "Como montar uma reserva de emergência?"
    response = http.post("/v1/chat/ask", json={"message": message})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == message
    assert data["answered"] is True
    assert data["status"] == "grounded"
    evidence = data["evidences"][0]
    assert any(
        source in evidence["source_name"]
        for source in (
            "Banco Central",
            "CVM",
            "Comissão de Valores",
            "CFPB",
            "Consumer Financial",
            "ANPD",
            "Proteção de Dados",
        )
    )
    assert evidence["source_url"] in data["answer"]
    assert evidence["document_id"].endswith(".txt")
    assert set(evidence) == {
        "id",
        "document_id",
        "source_name",
        "source_url",
        "document_title",
        "section",
        "content",
        "score",
    }
    assert isinstance(evidence["score"], float)


def test_pergunta_fora_do_escopo_abstem(client):
    http, _ = client
    response = http.post("/v1/chat/ask", json={"message": "receita de bolo de chocolate"})
    assert response.status_code == 200
    data = response.json()
    assert data["answered"] is False
    assert data["status"] == "abstained"
    assert data["evidences"] == []


def test_limiar_alto_abstem_com_dependencia_substituida(client, tmp_path):
    http, _ = client
    service = RAGService(
        threshold=0.99,
        embedder=FakeEmbedder(),
        store=SQLiteVectorStore(tmp_path / "threshold.db", dimension=2),
    )
    app.dependency_overrides[get_rag_service] = lambda: service
    response = http.post("/v1/chat/ask", json={"message": "Como montar uma reserva de emergência?"})
    assert response.status_code == 200
    assert response.json()["status"] == "abstained"
    assert response.json()["answered"] is False
    assert response.json()["evidences"] == []


@pytest.mark.parametrize(
    "payload", [{"message": ""}, {"message": "a" * 1001}, {}, {"message": None}]
)
def test_mensagem_invalida_retorna_422(client, payload):
    http, _ = client
    assert http.post("/v1/chat/ask", json=payload).status_code == 422


@pytest.mark.parametrize("message", ["a", "a" * 1000])
def test_limites_inclusivos_da_mensagem(client, message):
    http, _ = client
    assert http.post("/v1/chat/ask", json={"message": message}).status_code == 200
