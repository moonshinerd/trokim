"""Agente de documento: leitura local, abstenção e trilha sanitizada (#88)."""

import asyncio
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import settings
from app.domain.agents import AgentName, AgentStep, IssueSeverity, StepStatus, ValidationIssue
from app.domain.documents import (
    DocumentKind,
    DocumentQuality,
    ExtractedDocument,
    ExtractedField,
    ExtractedTransaction,
    FieldSource,
    QualityReport,
)
from app.models.vision_provider import OcrProvider, OcrWord, VisionProvider, VisionResult
from app.services.document_fields import (
    EXPECTED,
    TEXT_CONFIDENCE,
    VISION_REVIEW_CONFIDENCE,
    FieldCollection,
    TextExtraction,
    bb_continuation_header,
    normalized_value,
    parse_text,
)
from app.services.document_ocr import ocr_row_confidences, ocr_text_and_confidence
from app.services.document_reading import (
    DocumentPage,
    DocumentReadError,
    VisionSanitizer,
    image_bytes,
    read_pages,
    render_pdf_page,
)
from app.services.image_quality import MIN_OCR_CONFIDENCE, assess_quality


class DocumentContext(BaseModel):
    content: bytes = Field(exclude=True, repr=False)
    media_type: Literal["application/pdf", "image/jpeg", "image/png"]
    result: ExtractedDocument | None = None


class VisionFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: list[ExtractedField] = Field(max_length=20)


# Instrução explícita: chaves, formatos e exemplo. O JSON Schema do Pydantic sozinho não bastou:
# no benchmark de 27/11, a VLM local respondeu com chaves em português ("Banco"), outra fonte e
# dentro de bloco markdown, e toda contribuição foi descartada (#98).
VISION_INSTRUCTIONS = (
    "Leia a imagem deste comprovante, boleto ou fatura e extraia só os campos visíveis. "
    "Responda apenas com JSON, sem markdown e sem texto fora do JSON, exatamente neste formato: "
    '{"fields": [{"key": "amount", "value": "12.50", "confidence": 0.9, "source": "vlm"}]}. '
    "Chaves permitidas (em inglês, exatamente assim): date (data da operação), due_date "
    "(vencimento), amount (valor), total (total da fatura), counterparty (favorecido ou "
    "estabelecimento) e bank (banco). Datas no formato AAAA-MM-DD; valores com ponto decimal e "
    'duas casas, como texto. Use sempre "source": "vlm" e uma confiança entre 0 e 1. Omita o '
    "campo que não conseguir ler; nunca invente. Não inclua CPF, CNPJ, conta, agência nem "
    "trechos tarjados de preto."
)
_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class PageTrace(TypedDict):
    page: int
    status: str
    code: NotRequired[str]


@dataclass
class PageExtraction:
    text: TextExtraction
    collection: FieldCollection
    report: QualityReport
    engines: set[str] = field(default_factory=set)
    issues: list[ValidationIssue] = field(default_factory=list)
    failure: str | None = None


def warning(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, severity=IssueSeverity.WARNING, message=message)


def text_quality() -> QualityReport:
    return QualityReport(
        quality=DocumentQuality.LEGIBLE,
        sharpness=0,
        resolution=(0, 0),
        mean_ocr_confidence=None,
        reasons=[],
    )


class DocumentAgent:
    name = AgentName.DOCUMENT

    def __init__(
        self,
        ocr: OcrProvider | None = None,
        vision: VisionProvider | None = None,
        sanitizer: VisionSanitizer | None = None,
        timeout: float = 30,
        allow_remote: bool | None = None,
    ) -> None:
        self.ocr, self.vision, self.sanitizer = ocr, vision, sanitizer
        self.timeout = timeout
        # Consentimento para visão remota: por requisição (app) ou, sem ela, a configuração.
        self.allow_remote = settings.VISION_ALLOW_REMOTE if allow_remote is None else allow_remote

    async def run(self, ctx: DocumentContext) -> AgentStep:
        started = time.perf_counter()
        ctx.result = None
        try:
            result, pages = await self._extract(ctx)
            ctx.result = result
            return AgentStep(
                agent=self.name,
                status=StepStatus.ABSTAINED if result.abstained else StepStatus.OK,
                summary="Leitura encerrada; confira os avisos antes de confirmar.",
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail={
                    "engine": result.engine,
                    "pages": pages,
                    "fields": len(result.fields),
                    "issues": [item.code for item in result.issues],
                },
            )
        except Exception as error:
            code = (
                error.code if isinstance(error, DocumentReadError) else "DOCUMENT_PROCESSING_FAILED"
            )
            return AgentStep(
                agent=self.name,
                status=StepStatus.FAILED,
                summary="Não foi possível processar o documento.",
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail={"code": code},
            )
        finally:
            ctx.content = b""

    async def _extract(self, ctx: DocumentContext) -> tuple[ExtractedDocument, list[PageTrace]]:
        collection = FieldCollection()
        transactions: list[ExtractedTransaction] = []
        issues: list[ValidationIssue] = []
        reports: list[QualityReport] = []
        trace: list[PageTrace] = []
        engines: set[str] = set()
        kind = DocumentKind.OTHER
        failures: list[str] = []
        bb_header = ""
        for page in read_pages(ctx.content, ctx.media_type):
            result = await self._read_page(ctx.content, page, bb_header)
            if not bb_header:
                bb_header = bb_continuation_header(page.text or "")
            page_kind = result.text.kind
            if page_kind != DocumentKind.OTHER:
                if kind not in {DocumentKind.OTHER, page_kind}:
                    raise DocumentReadError("MIXED_DOCUMENT_KINDS")
                kind = page_kind
            elif result.report.quality != DocumentQuality.ILLEGIBLE:
                result.issues.append(warning("UNSUPPORTED_LAYOUT", "Layout não suportado."))
            for key in result.collection.conflicts:
                collection.values.pop(key, None)
                collection.conflicts.add(key)
            collection.merge(list(result.collection.values.values()))
            transactions.extend(result.text.transactions)
            issues.extend(result.issues)
            reports.append(result.report)
            engines.update(result.engines)
            page_trace: PageTrace = {
                "page": page.number,
                "status": (
                    "failed"
                    if result.failure
                    else "illegible"
                    if result.report.quality == DocumentQuality.ILLEGIBLE
                    else "+".join(sorted(result.engines)) or "quality_gate"
                ),
            }
            if result.failure:
                failures.append(result.failure)
                page_trace["code"] = result.failure
            trace.append(page_trace)
        if failures and not collection.values and not transactions:
            raise DocumentReadError(failures[0])
        if not reports:
            raise DocumentReadError("EMPTY_DOCUMENT")
        if collection.conflicts:
            issues.append(warning("FIELD_CONFLICT", "Campo divergente entre leituras; revise."))
        return self._finish(kind, collection, transactions, reports, issues, engines), trace

    async def _read_page(
        self, content: bytes, page: DocumentPage, bb_header: str
    ) -> PageExtraction:
        text = parse_text(
            page.text or "",
            FieldSource.TEXT_LAYER,
            TEXT_CONFIDENCE,
            bb_header=bb_header if page.text else "",
        )
        fields = FieldCollection()
        fields.merge(text.fields)
        result = PageExtraction(
            text,
            fields,
            text_quality(),
            {"text_layer"} if fields.values or text.transactions else set(),
        )
        image = page.image
        try:
            if text.sufficient(continuation=bool(bb_header)):
                return result
            image = image or render_pdf_page(content, page.number - 1)
            result.report = assess_quality(image)
            if result.report.quality == DocumentQuality.ILLEGIBLE:
                if fields.values or text.transactions:
                    result.report.quality = DocumentQuality.PARTIAL
                return result
            if self.ocr is None:
                raise DocumentReadError("OCR_UNAVAILABLE")
            try:
                reading = await asyncio.wait_for(self.ocr.read(image_bytes(image)), self.timeout)
            except TimeoutError:
                raise DocumentReadError("OCR_TIMEOUT") from None
            except Exception:
                raise DocumentReadError("OCR_UNAVAILABLE") from None
            ocr_text, confidences = ocr_text_and_confidence(reading)
            mean_confidence = reading.mean_confidence or 0.0
            ocr_text = parse_text(ocr_text, FieldSource.OCR, mean_confidence, bb_header=bb_header)
            if text.kind != DocumentKind.OTHER and ocr_text.kind not in {
                DocumentKind.OTHER,
                text.kind,
            }:
                raise DocumentReadError("MIXED_DOCUMENT_KINDS")
            if ocr_text.kind != DocumentKind.OTHER:
                result.text.kind = ocr_text.kind
            result.report = assess_quality(image, mean_confidence)
            candidates: list[ExtractedField] = []
            for item in ocr_text.fields:
                confidence = confidences.get(item.key, mean_confidence)
                if confidence >= MIN_OCR_CONFIDENCE:
                    candidates.append(item.model_copy(update={"confidence": confidence}))
                else:
                    result.issues.append(warning("LOW_CONFIDENCE", "Campo exige nova leitura."))
            fields.merge(candidates)
            # Não substitui silenciosamente linhas textuais por uma segunda leitura OCR.
            if not result.text.transactions:
                confidences_by_row = ocr_row_confidences(reading, len(ocr_text.transactions))
                for row, row_confidence in zip(
                    ocr_text.transactions,
                    confidences_by_row,
                    strict=True,
                ):
                    if row_confidence >= MIN_OCR_CONFIDENCE:
                        result.text.transactions.append(
                            row.model_copy(update={"confidence": row_confidence})
                        )
                    else:
                        result.issues.append(
                            warning("LOW_CONFIDENCE", "Lançamento exige nova leitura.")
                        )
            result.engines.add(reading.engine)
            expected = EXPECTED.get(result.text.kind, set())
            if (
                self.vision is not None
                and result.text.kind != DocumentKind.OTHER
                and (expected - fields.values.keys() or fields.conflicts)
            ):
                if await self._complement(image_bytes(image), fields, result.issues, reading.words):
                    result.engines.add("vlm")
            return result
        except DocumentReadError as error:
            if error.code == "MIXED_DOCUMENT_KINDS":
                raise
            result.failure = error.code
            result.report.quality = DocumentQuality.PARTIAL
            result.report.reasons.append("Leitura interrompida por falha técnica.")
            result.issues.append(
                warning(error.code, "Falha na leitura da página; revise o documento.")
            )
            return result
        finally:
            if image is not None:
                image.close()

    @staticmethod
    def _finish(
        kind: DocumentKind,
        fields: FieldCollection,
        transactions: list[ExtractedTransaction],
        reports: list[QualityReport],
        issues: list[ValidationIssue],
        engines: set[str],
    ) -> ExtractedDocument:
        incomplete = (
            bool(EXPECTED.get(kind, set()) - fields.values.keys())
            or (kind == DocumentKind.CARD_INVOICE and not transactions)
            or any(
                row.date is None or row.amount is None or not row.description
                for row in transactions
            )
            or any(item.confidence < MIN_OCR_CONFIDENCE for item in fields.values.values())
            or any(report.quality != DocumentQuality.LEGIBLE for report in reports)
        )
        if incomplete:
            issues.append(warning("INCOMPLETE_EXTRACTION", "Leitura incompleta; revise os campos."))
        abstained = not fields.values and not transactions
        all_illegible = all(report.quality == DocumentQuality.ILLEGIBLE for report in reports)
        quality = reports[0].model_copy(deep=True)
        quality.quality = (
            DocumentQuality.ILLEGIBLE
            if all_illegible
            else DocumentQuality.PARTIAL
            if incomplete or abstained or issues
            else DocumentQuality.LEGIBLE
        )
        quality.reasons = sorted({reason for report in reports for reason in report.reasons})
        reason = None
        if abstained:
            reason = (
                "Documento ilegível. Envie uma nova foto."
                if all_illegible
                else "Nenhum campo seguro identificado. Use um layout suportado "
                "ou preencha manualmente."
            )
        bank = fields.values.get("bank")
        return ExtractedDocument(
            kind=kind,
            bank=str(bank.value) if bank else None,
            quality=quality,
            fields=list(fields.values.values()),
            transactions=transactions,
            issues=issues,
            abstained=abstained,
            reason=reason,
            engine="+".join(sorted(engines)) or "quality_gate",
        )

    async def _complement(
        self,
        image: bytes,
        fields: FieldCollection,
        issues: list[ValidationIssue],
        words: list[OcrWord] | None = None,
    ) -> bool:
        vision = self.vision
        if vision is None:
            return False
        if vision.is_remote and not self.allow_remote:
            issues.append(warning("VISION_REMOTE_BLOCKED", "Visão remota exige consentimento."))
            return False
        if self.sanitizer is None:
            issues.append(warning("VISION_PRIVACY_BLOCKED", "Visão bloqueada por privacidade."))
            return False
        called = False
        try:
            safe_image = self.sanitizer.sanitize(image, words)
            if safe_image is None:
                issues.append(warning("VISION_PRIVACY_BLOCKED", "Visão bloqueada por privacidade."))
                return False
            called = True
            raw = await asyncio.wait_for(
                vision.extract(safe_image, VISION_INSTRUCTIONS),
                self.timeout,
            )
            if not isinstance(raw, VisionResult):
                raise ValueError("INVALID_VISION_OUTPUT")
            fenced = _JSON_FENCE.match(raw.content)
            proposed = VisionFields.model_validate_json(fenced[1] if fenced else raw.content)
            candidates: list[ExtractedField] = []
            keys: set[str] = set()
            # Valida e sanitiza tudo antes de modificar qualquer campo do OCR.
            for item in proposed.fields:
                if item.key in keys or item.source != FieldSource.VLM or item.value is None:
                    raise ValueError("INVALID_VISION_FIELDS")
                keys.add(item.key)
                raw_value = str(item.value)
                if isinstance(item.value, float):
                    if item.key not in {"amount", "total"}:
                        raise ValueError("INVALID_VISION_FIELDS")
                    decimal_value = Decimal(raw_value)
                    if decimal_value * 100 != (decimal_value * 100).to_integral_value():
                        raise ValueError("INVALID_VISION_FIELDS")
                    raw_value = format(decimal_value, ".2f")
                value = normalized_value(item.key, raw_value, canonical=True)
                if value is None:
                    raise ValueError("INVALID_VISION_FIELDS")
                candidates.append(
                    ExtractedField(
                        key=item.key,
                        value=value,
                        source=FieldSource.VLM,
                        confidence=min(item.confidence, VISION_REVIEW_CONFIDENCE),
                    )
                )
            before = set(fields.values)
            fields.merge(candidates)
            if fields.conflicts or set(fields.values) - before:
                issues.append(warning("VISION_REVIEW_REQUIRED", "Leitura de visão exige revisão."))
        except (ValidationError, ValueError, TimeoutError):
            issues.append(warning("INVALID_VISION_OUTPUT", "Contribuição de visão descartada."))
        except Exception:
            issues.append(
                warning("VISION_UNAVAILABLE", "Visão indisponível; leitura local preservada.")
            )
        return called
