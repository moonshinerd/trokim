"""Casos sintéticos do agente de documentos, sem OCR/modelo instalados."""

import io
from unittest.mock import AsyncMock

import numpy as np
import pytest
from PIL import Image
from reportlab.pdfgen import canvas

from app.domain.agents import StepStatus
from app.domain.documents import DocumentQuality
from app.models.vision_provider import OcrResult, OcrWord, VisionResult
from app.services.agents.document import DocumentAgent, DocumentContext
from app.services.image_quality import assess_quality

PIX = "Comprovante Pix\nData: 23/11/2026\nValor: R$ 12,50\nFavorecido: Pessoa Sintética\n"


def ocr_result(text, confidence, field_confidences=None):
    words = []
    for line in text.splitlines():
        from app.services.document_fields import LABELS

        key = LABELS.get(line.split(":", 1)[0].strip().casefold())
        value = (field_confidences or {}).get(key, confidence)
        words.append(OcrWord.model_construct(text=line, confidence=value, box=None))
    return OcrResult.model_construct(words=words, engine="ocr")


def picture(blank=False):
    data = (
        np.zeros((400, 400, 3), dtype=np.uint8)
        if blank
        else np.random.default_rng(7).integers(
            0,
            256,
            (400, 400, 3),
            dtype=np.uint8,
        )
    )
    image = Image.fromarray(data)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def pdf(texts):
    out = io.BytesIO()
    c = canvas.Canvas(out)
    for text in texts:
        for n, line in enumerate(text.splitlines()):
            c.drawString(50, 780 - n * 20, line)
        c.showPage()
    c.save()
    return out.getvalue()


async def extract(content=None, text=PIX, confidence=0.98, **kwargs):
    ocr = AsyncMock()
    ocr.read.return_value = ocr_result(text, confidence)
    ctx = DocumentContext(content=content or picture(), media_type="image/png")
    step = await DocumentAgent(ocr=ocr, **kwargs).run(ctx)
    return ctx, step, ocr


async def test_legible():
    ctx, step, _ = await extract()
    assert step.status == StepStatus.OK
    assert ctx.result.needs_review is True
    assert {f.key: f.value for f in ctx.result.fields}["amount"] == "12.50"
    assert ctx.result.quality.quality == DocumentQuality.LEGIBLE
    assert not ctx.content
    assert "Pessoa" not in step.model_dump_json()


async def test_illegible_abstains_before_ocr():
    ctx, step, ocr = await extract(content=picture(blank=True))
    assert ctx.result.abstained
    assert ctx.result.fields == ctx.result.transactions == []
    assert step.status == StepStatus.ABSTAINED
    ocr.read.assert_not_called()


async def test_partial_preserves_fields():
    ctx, _, _ = await extract(text=PIX.replace("Valor: R$ 12,50\n", ""))
    assert not ctx.result.abstained
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert "amount" not in {f.key for f in ctx.result.fields}


async def test_low_confidence_abstains_without_claiming_blur():
    ctx, _, _ = await extract(confidence=0.3)
    assert ctx.result.abstained
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert "ilegível" not in ctx.result.reason


async def test_unknown_layout():
    ctx, _, _ = await extract(text="Documento desconhecido\nValor: 12,50")
    assert ctx.result.abstained
    assert "UNSUPPORTED_LAYOUT" in [i.code for i in ctx.result.issues]


async def test_text_pdf_bypasses_ocr_and_vision():
    ocr, vision = AsyncMock(), AsyncMock()
    vision.is_remote = False
    ctx = DocumentContext(content=pdf([PIX]), media_type="application/pdf")
    step = await DocumentAgent(ocr=ocr, vision=vision).run(ctx)
    assert step.status == StepStatus.OK
    assert ctx.result.engine == "text_layer"
    ocr.read.assert_not_called()
    vision.extract.assert_not_called()


async def test_technical_error_is_sanitized():
    ocr = AsyncMock()
    ocr.read.side_effect = RuntimeError("CPF 123.456.789-00 payload secreto")
    ctx = DocumentContext(content=picture(), media_type="image/png")
    step = await DocumentAgent(ocr=ocr).run(ctx)
    assert step.status == StepStatus.FAILED
    assert ctx.result is None
    assert step.detail == {"code": "OCR_UNAVAILABLE"}
    assert "secreto" not in step.model_dump_json()
    assert ctx.content == b""


async def test_privacy_in_free_fields():
    ctx, _, _ = await extract(
        text=PIX.replace(
            "Pessoa Sintética",
            "Pessoa Sintética 123.456.789-00 conta 4567 agência 9999",
        )
    )
    raw = ctx.result.model_dump_json()
    assert "123" not in raw and "4567" not in raw and "9999" not in raw
    assert "Pessoa Sintética" in raw


async def test_invalid_image_and_content_excluded():
    ctx = DocumentContext(content=b"segredo", media_type="image/png")
    assert "segredo" not in repr(ctx) and "content" not in ctx.model_dump()
    step = await DocumentAgent().run(ctx)
    assert step.detail["code"] == "INVALID_IMAGE"
    assert ctx.content == b""


async def test_page_limit():
    ctx = DocumentContext(content=pdf([PIX] * 11), media_type="application/pdf")
    step = await DocumentAgent().run(ctx)
    assert step.detail["code"] == "PAGE_LIMIT"


async def test_mixed_pages(monkeypatch):
    monkeypatch.setattr(
        "app.services.agents.document.render_pdf_page",
        lambda *_: Image.new(
            "RGB",
            (400, 400),
            "white",
        ),
    )
    ctx = DocumentContext(content=pdf([PIX, ""]), media_type="application/pdf")
    step = await DocumentAgent().run(ctx)
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert len(ctx.result.fields) == 3
    assert step.detail["pages"][1] == {"page": 2, "status": "illegible"}


async def test_conflicting_pages_remove_field():
    ctx = DocumentContext(
        content=pdf([PIX, PIX.replace("12,50", "99,00")]), media_type="application/pdf"
    )
    await DocumentAgent().run(ctx)
    assert "amount" not in {f.key for f in ctx.result.fields}
    assert any(i.code == "FIELD_CONFLICT" for i in ctx.result.issues)


async def test_vision_blocked_without_sanitizer():
    vision = AsyncMock()
    vision.is_remote = False
    ctx, _, _ = await extract(text=PIX.replace("Data: 23/11/2026\n", ""), vision=vision)
    vision.extract.assert_not_called()
    assert any(i.code == "VISION_PRIVACY_BLOCKED" for i in ctx.result.issues)


class SyntheticSanitizer:
    def sanitize(self, image):
        return image


async def test_invalid_vision_preserves_ocr():
    vision = AsyncMock()
    vision.is_remote = False
    vision.extract.return_value = VisionResult(
        content=('{"cpf":"123.456.789-00"}'), model="mock-vision"
    )
    ctx, _, _ = await extract(
        text=PIX.replace("Data: 23/11/2026\n", ""), vision=vision, sanitizer=SyntheticSanitizer()
    )
    assert len(ctx.result.fields) == 2
    assert any(i.code == "INVALID_VISION_OUTPUT" for i in ctx.result.issues)
    assert "123.456" not in ctx.result.model_dump_json()


async def test_vision_conflict_never_overwrites():
    vision = AsyncMock()
    vision.is_remote = False
    vision.extract.return_value = VisionResult(
        content=('{"fields":[{"key":"amount","value":"99.00","confidence":1,"source":"vlm"}]}'),
        model="mock-vision",
    )
    ctx, _, _ = await extract(
        text=PIX.replace("Data: 23/11/2026\n", ""), vision=vision, sanitizer=SyntheticSanitizer()
    )
    assert "amount" not in {f.key for f in ctx.result.fields}
    assert any(i.code == "VISION_REVIEW_REQUIRED" for i in ctx.result.issues)


async def test_invalid_ocr_confidence():
    ctx, step, _ = await extract(confidence=float("nan"))
    assert step.detail["code"] == "INVALID_OCR_RESULT"
    assert ctx.result is None


async def test_ambiguous_amount_not_guessed():
    ctx, _, _ = await extract(text=PIX.replace("12,50", "12.50"))
    assert "amount" not in {f.key for f in ctx.result.fields}


def test_quality_does_not_claim_cut():
    report = assess_quality(Image.new("RGB", (20, 20), "white"))
    assert report.quality == DocumentQuality.ILLEGIBLE
    assert "texto cortado" not in report.reasons


async def test_boleto():
    ctx, _, _ = await extract(
        text="Boleto\nFavorecido: Pessoa Sintética\nValor: 20,00\nVencimento: 25/11/2026"
    )
    assert ctx.result.kind.value == "boleto"
    assert ctx.result.quality.quality == DocumentQuality.LEGIBLE


async def test_invoice_rows():
    ctx, _, _ = await extract(
        text="Fatura de cartão\nBanco: Banco Sintético\n"
        "Vencimento: 25/11/2026\nTotal: 20,00\n"
        "Lançamento: 23/11/2026 | Mercado CPF 123.456.789-00 | 20,00"
    )
    assert ctx.result.transactions[0].amount == 20
    assert ctx.result.transactions[0].description == "Mercado"
    assert ctx.result.quality.quality == DocumentQuality.LEGIBLE


async def test_complete_ocr_does_not_call_vision():
    vision = AsyncMock()
    vision.is_remote = False
    ctx, _, _ = await extract(vision=vision, sanitizer=SyntheticSanitizer())
    assert len(ctx.result.fields) == 3
    vision.extract.assert_not_called()


async def test_bb_profile_bypasses_image_engines():
    from tests.bb_samples import FATURA_PADRAO

    ocr, vision = AsyncMock(), AsyncMock()
    vision.is_remote = False
    ctx = DocumentContext(content=FATURA_PADRAO, media_type="application/pdf")
    step = await DocumentAgent(ocr=ocr, vision=vision).run(ctx)
    assert step.status == StepStatus.OK
    assert ctx.result.transactions
    assert ctx.result.engine == "text_layer"
    assert ctx.result.bank == "Banco do Brasil"
    assert next(f.value for f in ctx.result.fields if f.key == "due_date") == "2026-11-10"
    ocr.read.assert_not_called()
    vision.extract.assert_not_called()


async def test_missing_renderer_is_technical_failure(monkeypatch):
    from app.services.document_reading import DocumentReadError

    def unavailable(*args):
        raise DocumentReadError("PDF_RENDERER_UNAVAILABLE")

    monkeypatch.setattr("app.services.agents.document.render_pdf_page", unavailable)
    ctx = DocumentContext(content=pdf(["Somente cabeçalho"]), media_type="application/pdf")
    step = await DocumentAgent().run(ctx)
    assert step.status == StepStatus.FAILED
    assert step.detail["code"] == "PDF_RENDERER_UNAVAILABLE"


async def test_timeout_is_not_illegibility():
    import asyncio

    ocr = AsyncMock()

    async def slow(*args):
        await asyncio.sleep(1)

    ocr.read.side_effect = slow
    ctx = DocumentContext(content=picture(), media_type="image/png")
    step = await DocumentAgent(ocr=ocr, timeout=0.001).run(ctx)
    assert step.detail["code"] == "OCR_TIMEOUT"
    assert ctx.result is None


async def test_cancellation_clears_file():
    import asyncio

    ocr = AsyncMock()
    ocr.read.side_effect = asyncio.CancelledError()
    ctx = DocumentContext(content=picture(), media_type="image/png")
    with pytest.raises(asyncio.CancelledError):
        await DocumentAgent(ocr=ocr).run(ctx)
    assert ctx.content == b""


async def test_pixel_limit(monkeypatch):
    monkeypatch.setattr("app.services.document_reading.MAX_PIXELS", 10)
    ctx, step, _ = await extract()
    assert step.detail["code"] == "PIXEL_LIMIT"
    assert ctx.result is None


async def test_file_limit(monkeypatch):
    monkeypatch.setattr("app.services.document_reading.MAX_FILE_BYTES", 10)
    ctx, step, _ = await extract()
    assert step.detail["code"] == "FILE_LIMIT"


async def test_encrypted_pdf():
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf([PIX]))))
    writer.encrypt("senha-sintetica")
    out = io.BytesIO()
    writer.write(out)
    ctx = DocumentContext(content=out.getvalue(), media_type="application/pdf")
    step = await DocumentAgent().run(ctx)
    assert step.detail["code"] == "PASSWORD_PROTECTED"


async def test_bb_conflicting_metadata_is_not_chosen():
    from pypdf import PdfReader

    from tests.bb_samples import FATURA_PADRAO

    raw = PdfReader(io.BytesIO(FATURA_PADRAO)).pages[0].extract_text()
    content = pdf([raw + "\nVencimento 12/12/2026\nTotal da Fatura R$ 999,00"])
    ctx = DocumentContext(content=content, media_type="application/pdf")
    step = await DocumentAgent().run(ctx)
    assert step.status == StepStatus.OK
    assert {f.key for f in ctx.result.fields}.isdisjoint({"total", "due_date"})
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert any(i.code == "FIELD_CONFLICT" for i in ctx.result.issues)


async def test_text_header_uses_ocr_and_preserves_text_fields(monkeypatch):
    monkeypatch.setattr(
        "app.services.agents.document.render_pdf_page", lambda *_: Image.open(io.BytesIO(picture()))
    )
    ocr = AsyncMock()
    ocr.read.return_value = ocr_result(PIX, 0.98)
    ctx = DocumentContext(
        content=pdf(["Comprovante Pix\nBanco: Banco Sintético"]), media_type="application/pdf"
    )
    step = await DocumentAgent(ocr=ocr).run(ctx)
    assert step.status == StepStatus.OK
    ocr.read.assert_awaited_once()
    values = {f.key: f.value for f in ctx.result.fields}
    assert values["bank"] == "Banco Sintético"
    assert values["amount"] == "12.50"
    assert values["date"] == "2026-11-23"
    assert ctx.result.engine == "ocr+text_layer"


async def test_bb_partial_preserves_readable_first_page(monkeypatch):
    from pypdf import PdfReader

    from tests.bb_samples import FATURA_PADRAO

    monkeypatch.setattr(
        "app.services.agents.document.render_pdf_page",
        lambda *_: Image.new("RGB", (400, 400), "white"),
    )
    raw = PdfReader(io.BytesIO(FATURA_PADRAO)).pages[0].extract_text()
    ctx = DocumentContext(content=pdf([raw, ""]), media_type="application/pdf")
    step = await DocumentAgent().run(ctx)
    assert ctx.result.transactions
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert step.detail["pages"][1]["status"] == "illegible"


async def test_vision_adds_missing_field_as_review_proposal():
    vision = AsyncMock()
    vision.is_remote = False
    vision.extract.return_value = VisionResult(
        content=('{"fields":[{"key":"date","value":"2026-11-23","confidence":1,"source":"vlm"}]}'),
        model="mock-vision",
    )
    ctx, step, _ = await extract(
        text=PIX.replace("Data: 23/11/2026\n", ""), vision=vision, sanitizer=SyntheticSanitizer()
    )
    item = next(f for f in ctx.result.fields if f.key == "date")
    assert item.value == "2026-11-23"
    assert item.source.value == "vlm"
    assert item.confidence == 0.5
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert any(i.code == "VISION_REVIEW_REQUIRED" for i in ctx.result.issues)
    assert "vlm" in step.detail["engine"]


async def test_invalid_vision_batch_does_not_modify_ocr():
    vision = AsyncMock()
    vision.is_remote = False
    vision.extract.return_value = VisionResult(
        content=(
            '{"fields":[{"key":"amount","value":"99.00","confidence":1,"source":"vlm"},'
            '{"key":"date","value":"inválida","confidence":1,"source":"vlm"}]}'
        ),
        model="mock-vision",
    )
    ctx, _, _ = await extract(
        text=PIX.replace("Data: 23/11/2026\n", ""), vision=vision, sanitizer=SyntheticSanitizer()
    )
    assert next(f.value for f in ctx.result.fields if f.key == "amount") == "12.50"
    assert any(i.code == "INVALID_VISION_OUTPUT" for i in ctx.result.issues)


async def test_vision_free_fields_are_sanitized():
    vision = AsyncMock()
    vision.is_remote = False
    vision.extract.return_value = VisionResult(
        content=(
            '{"fields":[{"key":"counterparty","value":"Pessoa Sintética CPF 123.456.789-00",'
            '"confidence":1,"source":"vlm"}]}'
        ),
        model="mock-vision",
    )
    ctx, _, _ = await extract(
        text=PIX.replace("Favorecido: Pessoa Sintética\n", ""),
        vision=vision,
        sanitizer=SyntheticSanitizer(),
    )
    assert next(f.value for f in ctx.result.fields if f.key == "counterparty") == "Pessoa Sintética"
    assert "123.456" not in ctx.result.model_dump_json()


async def test_per_field_confidence_rejects_only_uncertain_field():
    ocr = AsyncMock()
    ocr.read.return_value = ocr_result(PIX, 0.98, {"amount": 0.2})
    ctx = DocumentContext(content=picture(), media_type="image/png")
    await DocumentAgent(ocr=ocr).run(ctx)
    assert {f.key for f in ctx.result.fields} == {"date", "counterparty"}
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert any(i.code == "LOW_CONFIDENCE" for i in ctx.result.issues)


async def test_ocr_conflict_does_not_reinsert_text_field(monkeypatch):
    monkeypatch.setattr(
        "app.services.agents.document.render_pdf_page", lambda *_: Image.open(io.BytesIO(picture()))
    )
    ocr = AsyncMock()
    ocr.read.return_value = ocr_result(PIX.replace("12,50", "99,00"), 0.98)
    text = PIX.replace("Data: 23/11/2026\n", "")
    ctx = DocumentContext(content=pdf([text, PIX]), media_type="application/pdf")
    await DocumentAgent(ocr=ocr).run(ctx)
    assert "amount" not in {f.key for f in ctx.result.fields}
    assert any(i.code == "FIELD_CONFLICT" for i in ctx.result.issues)


async def test_incomplete_invoice_row_is_partial():
    ctx, _, _ = await extract(
        text="Fatura de cartão\nBanco: Banco Sintético\n"
        "Vencimento: 25/11/2026\nTotal: 20,00\nLançamento: inválida | Loja | indefinido"
    )
    assert ctx.result.quality.quality == DocumentQuality.PARTIAL
    assert any(i.code == "INCOMPLETE_EXTRACTION" for i in ctx.result.issues)


async def test_vision_numeric_amount_is_normalized_without_rounding():
    vision = AsyncMock()
    vision.is_remote = False
    vision.extract.return_value = VisionResult(
        content=('{"fields":[{"key":"amount","value":12.5,"confidence":1,"source":"vlm"}]}'),
        model="mock-vision",
    )
    ctx, _, _ = await extract(
        text=PIX.replace("Valor: R$ 12,50\n", ""), vision=vision, sanitizer=SyntheticSanitizer()
    )
    item = next(f for f in ctx.result.fields if f.key == "amount")
    assert item.value == "12.50"
    assert item.confidence == 0.5


@pytest.mark.parametrize("value", ["12.501", "true", '"12,5"'])
async def test_vision_rejects_ambiguous_or_invalid_amount(value):
    vision = AsyncMock()
    vision.is_remote = False
    vision.extract.return_value = VisionResult(
        content=(
            '{"fields":[{"key":"amount","value":' + value + ',"confidence":1,"source":"vlm"}]}'
        ),
        model="mock-vision",
    )
    ctx, _, _ = await extract(
        text=PIX.replace("Valor: R$ 12,50\n", ""), vision=vision, sanitizer=SyntheticSanitizer()
    )
    assert "amount" not in {f.key for f in ctx.result.fields}
    assert any(i.code == "INVALID_VISION_OUTPUT" for i in ctx.result.issues)
