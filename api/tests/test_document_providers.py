"""Integração do agente com os contratos e mocks públicos da #87."""

import io

import pytest
from PIL import Image

from app.clients.mock_vision import MockOcrProvider, MockVisionProvider
from app.clients.vision_factory import RemoteVisionNotAllowedError
from app.core.config import settings
from app.domain.agents import StepStatus
from app.domain.documents import DocumentQuality, FieldSource
from app.models.vision_provider import OcrResult, OcrWord
from app.services.agents.document import DocumentAgent, DocumentContext
from app.services.document_factory import get_document_agent
from app.services.document_ocr import ocr_text_and_confidence
from app.services.document_reading import render_pdf_page
from tests.test_document_agent import PIX, SyntheticSanitizer, pdf, picture


async def test_agent_accepts_public_ocr_and_vision_mocks():
    ocr = MockOcrProvider(
        [(line, 0.99) for line in PIX.splitlines() if not line.startswith("Data:")]
    )
    vision = MockVisionProvider(
        fields={
            "fields": [
                {"key": "date", "value": "2026-11-23", "source": "vlm", "confidence": 1},
            ]
        }
    )
    ctx = DocumentContext(content=picture(), media_type="image/png")
    step = await DocumentAgent(ocr, vision, SyntheticSanitizer()).run(ctx)
    assert step.status == StepStatus.OK
    assert ctx.result.engine == "mock+vlm"
    proposal = next(item for item in ctx.result.fields if item.key == "date")
    assert proposal.source == FieldSource.VLM
    assert proposal.confidence == 0.5
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL


def test_factory_uses_real_ports_and_configuration(monkeypatch):
    monkeypatch.setattr(settings, "OCR_PROVIDER", "mock")
    monkeypatch.setattr(settings, "VISION_PROVIDER", "none")
    agent = get_document_agent()
    assert isinstance(agent.ocr, MockOcrProvider)
    assert agent.vision is None


def test_factory_rejects_remote_vision_without_consent(monkeypatch):
    monkeypatch.setattr(settings, "OCR_PROVIDER", "mock")
    monkeypatch.setattr(settings, "VISION_PROVIDER", "litellm")
    monkeypatch.setattr(settings, "VISION_MODEL", "openrouter/qwen/qwen2.5-vl-72b-instruct")
    monkeypatch.setattr(settings, "VISION_ALLOW_REMOTE", False)
    with pytest.raises(RemoteVisionNotAllowedError):
        get_document_agent()


async def test_direct_injection_cannot_bypass_remote_consent(monkeypatch):
    class RemoteMock(MockVisionProvider):
        is_remote = True

        async def extract(self, *args, **kwargs):
            pytest.fail("Não deve enviar pixels sem consentimento")

    monkeypatch.setattr(settings, "VISION_ALLOW_REMOTE", False)
    ocr = MockOcrProvider([("Comprovante Pix", 0.99), ("Valor: 12,50", 0.99)])
    ctx = DocumentContext(content=picture(), media_type="image/png")
    await DocumentAgent(ocr, RemoteMock(), SyntheticSanitizer()).run(ctx)
    assert any(issue.code == "VISION_REMOTE_BLOCKED" for issue in ctx.result.issues)


def test_ocr_boxes_reconstruct_label_value_and_field_confidence():
    reading = OcrResult(
        engine="mock",
        words=[
            OcrWord(text="12,50", confidence=0.6, box=(100, 50, 170, 70)),
            OcrWord(text="Comprovante Pix", confidence=0.99, box=(10, 10, 180, 30)),
            OcrWord(text="Valor:", confidence=0.99, box=(10, 50, 70, 70)),
        ],
    )
    text, confidence = ocr_text_and_confidence(reading)
    assert text == "Comprovante Pix\nValor: 12,50"
    assert confidence["amount"] == 0.6


async def test_empty_ocr_abstains_without_technical_failure():
    ctx = DocumentContext(content=picture(), media_type="image/png")
    step = await DocumentAgent(MockOcrProvider([])).run(ctx)
    assert step.status == StepStatus.ABSTAINED
    assert ctx.result.fields == []


def test_real_pdf_renderer_preserves_page_in_memory():
    pytest.importorskip("pypdfium2")
    image = render_pdf_page(pdf([PIX]), 0)
    try:
        assert min(image.size) > 320
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        with Image.open(io.BytesIO(buffer.getvalue())) as decoded:
            assert decoded.size == image.size
    finally:
        image.close()


async def test_bb_context_cannot_mask_another_document_kind():
    from pypdf import PdfReader

    from tests.bb_samples import FATURA_PADRAO

    raw = PdfReader(io.BytesIO(FATURA_PADRAO)).pages[0].extract_text()
    ctx = DocumentContext(content=pdf([raw, PIX]), media_type="application/pdf")
    step = await DocumentAgent().run(ctx)
    assert step.status == StepStatus.FAILED
    assert step.detail["code"] == "MIXED_DOCUMENT_KINDS"
    assert ctx.result is None


async def test_low_confidence_invoice_row_cannot_use_global_average():
    words = [
        ("Fatura de cartão", 0.99),
        ("Banco: Banco Sintético", 0.99),
        ("Vencimento: 25/11/2026", 0.99),
        ("Total: 20,00", 0.99),
        ("Lançamento: 23/11/2026 | Loja | 20,00", 0.2),
    ]
    ctx = DocumentContext(content=picture(), media_type="image/png")
    step = await DocumentAgent(MockOcrProvider(words)).run(ctx)
    assert step.status == StepStatus.OK
    assert ctx.result.transactions == []
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert any(issue.code == "LOW_CONFIDENCE" for issue in ctx.result.issues)


async def test_page_ocr_failure_preserves_previous_textual_fields(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "app.services.agents.document.render_pdf_page", lambda *_: Image.open(io.BytesIO(picture()))
    )
    ocr = AsyncMock()
    ocr.read.side_effect = TimeoutError()
    ctx = DocumentContext(content=pdf([PIX, ""]), media_type="application/pdf")
    step = await DocumentAgent(ocr=ocr).run(ctx)
    assert step.status == StepStatus.OK
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert next(item.value for item in ctx.result.fields if item.key == "amount") == "12.50"
    assert step.detail["pages"][1] == {"page": 2, "status": "failed", "code": "OCR_TIMEOUT"}
    assert ctx.result.quality.quality != DocumentQuality.ILLEGIBLE
