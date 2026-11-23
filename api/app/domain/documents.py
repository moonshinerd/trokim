"""Contrato de documentos do épico #86, compartilhado com #87 e #89."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.agents import AgentStep, ValidationIssue
from app.domain.models import TransactionCategory, TransactionType

# Transaction.source_kind dos lançamentos criados a partir de um documento confirmado.
DOCUMENT_SOURCE = "documento"


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


class DocumentExtractResponse(BaseModel):
    """Resposta de ``POST /v1/documents/extract``: o lido, a validação e a trilha dos passos."""

    document: ExtractedDocument
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    # Só vale confirmar se o documento não se absteve e nenhum aviso é bloqueio.
    can_confirm: bool
    steps: list[AgentStep] = Field(default_factory=list)
    total_ms: int = 0


class DocumentConfirmRequest(BaseModel):
    """Campos **revisados pelo usuário**; o app manda o que está na tela, não o que o OCR leu."""

    model_config = ConfigDict(extra="forbid")
    kind: DocumentKind = DocumentKind.OTHER
    date: date
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    type: TransactionType = TransactionType.DEBIT
    bank: str | None = Field(default=None, max_length=60)
    category: TransactionCategory | None = None


class DocumentConfirmResponse(BaseModel):
    outcome: Literal["criado", "repetido"]
    uid: str
    account_id: str
    category: TransactionCategory
    message: str
