"""Fluxo HTTP de documentos com dados sintéticos (#96)."""

import logging
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from test_agents_api import GroundedMockLLM
from test_document_agent import PIX, ocr_result, pdf, picture
from test_rag import FakeEmbedder

from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.core.config import settings
from app.main import app
from app.routers.v1 import documents as documents_router
from app.routers.v1.agents import get_orchestrator
from app.routers.v1.documents import get_document_pipeline
from app.services.agents.analysis import AnalysisAgent
from app.services.agents.communication import CommunicationAgent
from app.services.agents.document import DocumentAgent
from app.services.agents.document_pipeline import DocumentPipeline
from app.services.agents.orchestrator import Orchestrator
from app.services.agents.research import ResearchAgent
from app.services.agents.validation import ValidationAgent
from app.services.library_service import LIBRARY
from app.services.rag_service import RAGService

CONFIRM = {
    "kind": "pix_receipt",
    "date": "2026-11-20",
    "amount": "12.50",
    "description": "Padaria Sintética",
    "type": "debit",
}


def pipeline_with(ocr):
    return lambda: DocumentPipeline(DocumentAgent(ocr=ocr))


def ocr_for(text=PIX, confidence=0.98):
    ocr = AsyncMock()
    ocr.read.return_value = ocr_result(text, confidence)
    return ocr


@pytest.fixture
def client():
    previous = app.dependency_overrides.copy()
    LIBRARY.reset()
    app.dependency_overrides[get_document_pipeline] = pipeline_with(ocr_for())
    with TestClient(app) as c:
        yield c
    LIBRARY.reset()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def extract(client, content=None, name="a.png"):
    return client.post(
        "/v1/documents/extract",
        files={"file": (name, content or picture(), "application/octet-stream")},
    )


def test_extrai_documento_legivel(client):
    resp = extract(client)
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_confirm"] is True
    assert data["document"]["needs_review"] is True
    amount = {f["key"]: f["value"] for f in data["document"]["fields"]}["amount"]
    assert amount == "12.50"
    assert [s["agent"] for s in data["steps"]][0] == "document"
    assert LIBRARY.transactions == []  # extrair nunca cria nada


def test_extrai_pdf(client):
    resp = extract(client, pdf([PIX]), "a.pdf")
    assert resp.status_code == 200
    assert resp.json()["document"]["fields"]


def test_ilegivel_abstem_e_nada_e_criado(client):
    resp = extract(client, picture(blank=True))
    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["abstained"] is True
    assert data["can_confirm"] is False
    assert data["document"]["fields"] == []
    assert LIBRARY.transactions == []


def test_extrair_confirmar_cria_uma_vez_e_reenvio_e_repetido(client):
    assert extract(client).status_code == 200
    first = client.post("/v1/documents/confirm", json=CONFIRM)
    assert first.status_code == 200
    assert first.json()["outcome"] == "criado"
    again = client.post("/v1/documents/confirm", json=CONFIRM)
    assert again.status_code == 200
    assert again.json()["outcome"] == "repetido"
    assert again.json()["uid"] == first.json()["uid"]
    assert len(LIBRARY.transactions) == 1
    assert LIBRARY.transactions[0].origin == "documento"
    assert LIBRARY.transactions[0].source_kind == "conta"


def test_arquivo_grande_demais_413(client, monkeypatch):
    monkeypatch.setattr(documents_router, "MAX_FILE_BYTES", 100)
    resp = extract(client)
    assert resp.status_code == 413
    assert resp.json()["detail"]["code"] == "FILE_LIMIT"


def test_tipo_sem_magic_415(client):
    resp = extract(client, b"isto nao e imagem nem pdf", "a.png")
    assert resp.status_code == 415
    assert resp.json()["detail"]["code"] == "UNSUPPORTED_TYPE"


def test_ocr_indisponivel_503(client):
    ocr = AsyncMock()
    ocr.read.side_effect = RuntimeError("segredo interno")
    app.dependency_overrides[get_document_pipeline] = pipeline_with(ocr)
    resp = extract(client)
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "OCR_UNAVAILABLE"
    assert "segredo interno" not in resp.text


def test_confirmacao_bloqueada_pelo_validador_422(client):
    resp = client.post("/v1/documents/confirm", json={**CONFIRM, "date": "2099-01-01"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "CONFIRMATION_BLOCKED"
    assert detail["issues"]
    assert LIBRARY.transactions == []


@pytest.mark.parametrize(
    "body",
    [
        {**CONFIRM, "amount": "0"},
        {**CONFIRM, "amount": "-3"},
        {**CONFIRM, "description": "  "},
        {**CONFIRM, "extra": 1},
        {"kind": "pix_receipt"},
    ],
)
def test_corpo_invalido_422(client, body):
    assert client.post("/v1/documents/confirm", json=body).status_code == 422
    assert LIBRARY.transactions == []


def test_nada_do_arquivo_sobra_em_log_resposta_ou_disco(client, caplog, tmp_path, monkeypatch):
    import base64
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    content = picture()
    with caplog.at_level(logging.DEBUG):
        resp = extract(client, content)
    assert resp.status_code == 200
    assert base64.b64encode(content[:60]).decode() not in resp.text
    assert "iVBORw0KGgo" not in resp.text
    assert "iVBORw0KGgo" not in caplog.text
    assert list(tmp_path.iterdir()) == []


def test_ponta_a_ponta_extrair_confirmar_perguntar(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RAG_HYBRID_ALPHA", 0.0)
    rag = RAGService(embedder=FakeEmbedder(), store=SQLiteVectorStore(tmp_path / "e.db", 2))
    llm = GroundedMockLLM(model_name="mock-test")
    app.dependency_overrides[get_orchestrator] = lambda: Orchestrator(
        research=ResearchAgent(rag_service=rag),
        analysis=AnalysisAgent(),
        communication=CommunicationAgent(llm_provider=llm),
        validation=ValidationAgent(),
    )
    document = extract(client).json()["document"]
    fields = {field["key"]: field["value"] for field in document["fields"]}
    reviewed = {**CONFIRM, "amount": fields["amount"], "date": fields["date"]}
    uid = client.post("/v1/documents/confirm", json=reviewed).json()["uid"]
    client.post("/v1/documents/confirm", json={**reviewed, "description": "Outra loja"})
    data = client.post(
        "/v1/agents/ask", json={"message": "Quanto gastei nessa loja?", "document_uid": uid}
    ).json()
    assert data["status"] == "answered"
    assert data["calculations"][0]["value"] == 12.5
    assert uid in data["answer"]
    assert data["steps"][0]["detail"]["document_uids"] == [uid]
    assert "confirmado por você" in data["steps"][0]["summary"]


def test_fatura_revisada_total_e_reenvio(client):
    lines = [
        {"date": CONFIRM["date"], "description": name, "amount": "6.25"}
        for name in ("Loja A", "Loja B")
    ]
    body = {**CONFIRM, "kind": "card_invoice", "due_date": "2026-11-30", "transactions": lines}
    assert client.post("/v1/documents/confirm", json={**body, "amount": "12"}).status_code == 422
    assert not LIBRARY.transactions
    first = client.post("/v1/documents/confirm", json=body).json()
    again = client.post("/v1/documents/confirm", json=body).json()
    assert again["outcome"] == "repetido"
    assert len(set(first["uids"])) == 2
    assert again["uids"] == first["uids"]


def test_upload_maior_que_spool_padrao_fica_em_memoria(client, monkeypatch):
    from tempfile import SpooledTemporaryFile

    def sem_disco(self):
        pytest.fail("A imagem seria gravada em disco")

    monkeypatch.setattr(SpooledTemporaryFile, "rollover", sem_disco)
    assert extract(client, picture() + bytes(2 * 1024 * 1024)).status_code == 200
