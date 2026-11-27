"""Origem manual, conciliação com o extrato, escolha do motor e tarja dos pixels (#97, #117)."""

import io
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from nubank_samples import extrato_conta, lancamento
from PIL import Image
from test_document_agent import PIX, SyntheticSanitizer, extract, picture
from test_documents_api import CONFIRM, ocr_for, pipeline_with

from app.core.config import settings
from app.domain.documents import DocumentConfirmRequest
from app.domain.models import TransactionOrigin
from app.main import app
from app.models.vision_provider import OcrWord, VisionResult
from app.routers.v1.documents import get_document_pipeline, get_vision_pipeline_factory
from app.services.agent_query_service import (
    DOCUMENT_ORIGIN,
    MANUAL_ORIGIN,
    MIXED_ORIGIN,
    origin_text,
)
from app.services.agents.document import DocumentAgent
from app.services.agents.document_pipeline import DocumentPipeline
from app.services.calculation_service import CalculationService
from app.services.document_confirmation import confirm_document
from app.services.document_factory import (
    RemoteConsentRequiredError,
    VisionUnavailableError,
    get_document_agent,
)
from app.services.import_service import ImportService
from app.services.library_service import LIBRARY, Library
from app.services.vision_sanitizer import OcrMaskingSanitizer, sensitive_boxes


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


# --- #117: origem manual -------------------------------------------------------------------


def test_confirmacao_manual_grava_origem_manual(client):
    resp = client.post("/v1/documents/confirm", json={**CONFIRM, "origin": "manual"})
    assert resp.status_code == 200
    assert LIBRARY.transactions[0].origin == TransactionOrigin.MANUAL


def test_confirmacao_sem_origem_continua_documento(client):
    assert client.post("/v1/documents/confirm", json=CONFIRM).status_code == 200
    assert LIBRARY.transactions[0].origin == TransactionOrigin.DOCUMENT


def test_origem_invalida_422(client):
    resp = client.post("/v1/documents/confirm", json={**CONFIRM, "origin": "ocr"})
    assert resp.status_code == 422


def test_texto_da_origem_no_chat():
    library = Library()
    doc = DocumentConfirmRequest.model_validate(CONFIRM)
    manual = DocumentConfirmRequest.model_validate(
        {**CONFIRM, "description": "Feira Sintética", "origin": "manual"}
    )
    confirm_document(library, doc)
    confirm_document(library, manual)
    by_origin = {tx.origin: tx for tx in library.transactions}
    assert origin_text([by_origin[TransactionOrigin.DOCUMENT]]) == DOCUMENT_ORIGIN
    assert origin_text([by_origin[TransactionOrigin.MANUAL]]) == MANUAL_ORIGIN
    assert origin_text(library.transactions) == MIXED_ORIGIN


def test_chat_descreve_lancamento_digitado(client):
    manual = {**CONFIRM, "origin": "manual"}
    assert client.post("/v1/documents/confirm", json=manual).status_code == 200
    resp = client.post("/v1/agents/ask", json={"message": "quanto gastei na Padaria Sintética?"})
    assert resp.status_code == 200
    data = resp.json()
    assert MANUAL_ORIGIN in data["answer"]
    assert "Lido de foto" not in data["answer"]


# --- #117: comprovante confirmado e depois o extrato do mesmo Pix ---------------------------


def _ofx_pix(valor: str = "-12.50", data: str = "20261120") -> bytes:
    return extrato_conta(
        [
            lancamento(
                "DEBIT",
                data,
                valor,
                "p1",
                "Transferência enviada pelo Pix - PADARIA SINTETICA - 11.111.111/0001-11 - "
                "BANCO X (0001) Agência: 1 Conta: 123456-7",
            )
        ],
        inicio="20261101",
        fim="20261130",
    )


def _gasto_total(library: Library) -> Decimal:
    return Decimal(str(CalculationService.calculate_summary(library.transactions).total_expenses))


@pytest.mark.parametrize("origin", ["documento", "manual"])
def test_extrato_depois_do_comprovante_nao_conta_duas_vezes(origin):
    library = Library()
    confirm_document(library, DocumentConfirmRequest.model_validate({**CONFIRM, "origin": origin}))
    result = ImportService.import_ofx(library, _ofx_pix(), "nubank.ofx")
    assert result["documents_reconciled"] == 1
    assert _gasto_total(library) == Decimal("12.50")
    doc = next(tx for tx in library.transactions if tx.origin != TransactionOrigin.IMPORT)
    assert doc.is_duplicate is True


@pytest.mark.parametrize(("valor", "data"), [("-12.51", "20261120"), ("-12.50", "20261121")])
def test_extrato_com_valor_ou_data_diferente_nao_concilia(valor, data):
    library = Library()
    confirm_document(library, DocumentConfirmRequest.model_validate(CONFIRM))
    result = ImportService.import_ofx(library, _ofx_pix(valor, data), "nubank.ofx")
    assert result["documents_reconciled"] == 0
    assert sum(1 for tx in library.transactions if tx.counts_in_totals) == 2


def test_extrato_com_outro_favorecido_nao_concilia():
    library = Library()
    req = {**CONFIRM, "description": "Mercado Diferente"}
    confirm_document(library, DocumentConfirmRequest.model_validate(req))
    assert ImportService.import_ofx(library, _ofx_pix(), "nubank.ofx")["documents_reconciled"] == 0


def test_upload_informa_conciliacao(client):
    assert client.post("/v1/documents/confirm", json=CONFIRM).status_code == 200
    resp = client.post(
        "/v1/transactions/upload",
        files={"file": ("nubank.ofx", _ofx_pix(), "application/octet-stream")},
    )
    assert resp.status_code == 200
    assert resp.json()["documents_reconciled"] == 1


# --- #97: escolha do motor e consentimento ---------------------------------------------------


def test_motores_sem_visao_configurada(client, monkeypatch):
    monkeypatch.setattr(settings, "VISION_PROVIDER", "none")
    resp = client.get("/v1/documents/engines")
    assert resp.status_code == 200
    assert resp.json()["vision"] is None
    assert resp.json()["ocr"] == settings.OCR_PROVIDER


def test_motores_com_visao_remota(client, monkeypatch):
    monkeypatch.setattr(settings, "VISION_PROVIDER", "litellm")
    monkeypatch.setattr(settings, "VISION_MODEL", "openrouter/sintetico/vlm")
    monkeypatch.setattr(settings, "VISION_ALLOW_REMOTE", False)
    vision = client.get("/v1/documents/engines").json()["vision"]
    assert vision == {"model": "openrouter/sintetico/vlm", "remote": True}


def test_fabrica_exige_visao_e_consentimento(monkeypatch):
    monkeypatch.setattr(settings, "VISION_PROVIDER", "none")
    with pytest.raises(VisionUnavailableError):
        get_document_agent(engine="vision")
    monkeypatch.setattr(settings, "VISION_PROVIDER", "litellm")
    monkeypatch.setattr(settings, "VISION_MODEL", "openrouter/sintetico/vlm")
    with pytest.raises(RemoteConsentRequiredError):
        get_document_agent(engine="vision", allow_remote=False)
    agent = get_document_agent(engine="vision", allow_remote=True)
    assert agent.vision is not None and agent.allow_remote is True
    assert isinstance(agent.sanitizer, OcrMaskingSanitizer)
    assert get_document_agent(engine="ocr").vision is None


def _extract(client, **fields):
    return client.post(
        "/v1/documents/extract",
        files={"file": ("a.png", picture(), "application/octet-stream")},
        data=fields,
    )


def test_visao_sem_modelo_503(client, monkeypatch):
    monkeypatch.setattr(settings, "VISION_PROVIDER", "none")
    resp = _extract(client, engine="vision")
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "VISION_UNAVAILABLE"


def test_visao_remota_sem_consentimento_403(client, monkeypatch):
    monkeypatch.setattr(settings, "VISION_PROVIDER", "litellm")
    monkeypatch.setattr(settings, "VISION_MODEL", "openrouter/sintetico/vlm")
    resp = _extract(client, engine="vision", allow_remote="false")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "REMOTE_CONSENT_REQUIRED"


def test_visao_usa_o_pipeline_com_consentimento(client):
    chamadas = []

    def fabrica(allow_remote):
        chamadas.append(allow_remote)
        return DocumentPipeline(DocumentAgent(ocr=ocr_for()))

    app.dependency_overrides[get_vision_pipeline_factory] = lambda: fabrica
    resp = _extract(client, engine="vision", allow_remote="true")
    assert resp.status_code == 200
    assert chamadas == [True]


@pytest.mark.parametrize("fields", [{"engine": "gpt"}, {"allow_remote": "sim"}])
def test_campos_invalidos_422(client, fields):
    assert _extract(client, **fields).status_code == 422


async def test_consentimento_por_instancia_libera_visao_remota(monkeypatch):
    monkeypatch.setattr(settings, "VISION_ALLOW_REMOTE", False)
    vision = AsyncMock()
    vision.is_remote = True
    vision.extract.return_value = VisionResult(content='{"date": "2026-11-23"}', model="m")
    ctx, _, _ = await extract(
        text=PIX.replace("Data: 23/11/2026\n", ""),
        vision=vision,
        sanitizer=SyntheticSanitizer(),
        allow_remote=True,
    )
    vision.extract.assert_called_once()
    assert not any(i.code == "VISION_REMOTE_BLOCKED" for i in ctx.result.issues)


# --- tarja dos pixels -------------------------------------------------------------------------


def _png(width=400, height=120) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def test_tarja_documento_conta_e_valor_ao_lado_do_rotulo():
    words = [
        OcrWord(text="CPF ***.123.456-**", confidence=0.9, box=(10, 10, 120, 30)),
        OcrWord(text="Agência:", confidence=0.9, box=(10, 40, 80, 60)),
        OcrWord(text="1234", confidence=0.9, box=(90, 40, 130, 60)),
        OcrWord(text="Conta 56789-0", confidence=0.9, box=(10, 70, 140, 90)),
        OcrWord(text="Valor: R$ 12,50", confidence=0.9, box=(200, 10, 330, 30)),
        OcrWord(text="23/11/2026", confidence=0.9, box=(200, 40, 300, 60)),
        OcrWord(text="12.345.678/0001-90", confidence=0.9, box=(200, 70, 380, 90)),
    ]
    boxes = sensitive_boxes(words)
    assert (10, 10, 120, 30) in boxes
    assert (90, 40, 130, 60) in boxes  # o número ao lado do rótulo sozinho
    assert (10, 70, 140, 90) in boxes
    assert (200, 70, 380, 90) in boxes
    assert (200, 10, 330, 30) not in boxes  # valor e data continuam visíveis para a visão
    assert (200, 40, 300, 60) not in boxes

    masked = OcrMaskingSanitizer().sanitize(_png(), words)
    image = Image.open(io.BytesIO(masked)).convert("RGB")
    assert image.getpixel((50, 20)) == (0, 0, 0)
    assert image.getpixel((250, 20)) == (255, 255, 255)


def test_sem_caixas_do_ocr_bloqueia_a_visao():
    assert OcrMaskingSanitizer().sanitize(_png(), None) is None
    assert OcrMaskingSanitizer().sanitize(_png(), [OcrWord(text="x", confidence=1)]) is None
