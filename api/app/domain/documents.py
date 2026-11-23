"""Contrato de documentos do épico #86, compartilhado com #87 e #89."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.agents import ValidationIssue


class DocumentKind(StrEnum):
    PIX_RECEIPT = "pix_receipt"
    BOLETO = "boleto"
    CARD_INVOICE = "card_invoice"
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"


class DocumentQuality(StrEnum):
    LEGIBLE = "legible"
    PARTIAL = "partial"
    ILLEGIBLE = "illegible"


class FieldSource(StrEnum):
    TEXT_LAYER = "text_layer"
    OCR = "ocr"
    VLM = "vlm"


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    key: str
    value: str | float | None
    confidence: float = Field(ge=0, le=1)
    source: FieldSource


class ExtractedTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    date: date | None
    description: str
    amount: float | None
    installment: str | None = None
    confidence: float = Field(ge=0, le=1)


class QualityReport(BaseModel):
    quality: DocumentQuality
    sharpness: float
    resolution: tuple[int, int]
    mean_ocr_confidence: float | None
    reasons: list[str]


class ExtractedDocument(BaseModel):
    kind: DocumentKind
    bank: str | None
    quality: QualityReport
    fields: list[ExtractedField]
    transactions: list[ExtractedTransaction] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    needs_review: Literal[True] = True
    abstained: bool
    reason: str | None
    engine: str
