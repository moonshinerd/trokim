"""Contratos de domínio para extração e validação de documentos multimodais.

Parte do Épico #86 (Semana 5 — Multimodalidade).
Define o contrato de ExtractedDocument, ExtractedLine e DocumentType para representação
estruturada de faturas, boletos e comprovantes de Pix lidos via OCR/VLM.
"""

from __future__ import annotations

from datetime import date as dt_date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class DocumentType(StrEnum):
    """Tipos de documentos suportados no pipeline multimodal."""

    FATURA = "fatura"
    PIX = "pix"
    BOLETO = "boleto"
    OUTRO = "outro"


class ExtractedLine(BaseModel):
    """Item ou lançamento individual extraído de um documento (ex.: linha de fatura)."""

    description: str = ""
    amount: Decimal | float | str = Field(default=Decimal("0.00"))
    raw_amount: str | None = None
    date: dt_date | str | None = None
    category: str | None = None
    merchant: str | None = None
    confidence: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_amount(cls, data: Any) -> Any:
        if isinstance(data, dict):
            amt = data.get("amount")
            if isinstance(amt, str) and not data.get("raw_amount"):
                data["raw_amount"] = amt
        return data


class ExtractedDocument(BaseModel):
    """Documento financeiro estruturado extraído de imagem ou PDF escaneado."""

    document_type: DocumentType | str = DocumentType.OUTRO
    total_amount: Decimal | float | str | None = None
    amount: Decimal | float | str | None = None
    raw_amount: str | None = None
    currency: str = "BRL"
    date: dt_date | str | None = None
    issue_date: dt_date | str | None = None
    due_date: dt_date | str | None = None
    recipient: str | None = None  # favorecido / beneficiário
    sender: str | None = None  # pagador / emissor
    merchant: str | None = None  # estabelecimento comercial / favorecido
    institution: str | None = None  # banco emissor ou instituição financeira
    account_id: str | None = None  # identificador da conta associada
    barcode: str | None = None  # código de barras ou linha digitável
    confidence: float | None = None  # nível de confiança global da extração (0.0 a 1.0)
    lines: list[ExtractedLine] = Field(default_factory=list)
    is_invoice_payment: bool = False
    raw_text: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Preserva raw_amount se amount/total_amount vier como string
            raw_cand = data.get("raw_amount")
            if not raw_cand:
                if isinstance(data.get("amount"), str):
                    data["raw_amount"] = data["amount"]
                elif isinstance(data.get("total_amount"), str):
                    data["raw_amount"] = data["total_amount"]

            # Sincroniza amount e total_amount caso apenas um tenha sido informado
            if data.get("amount") is None and data.get("total_amount") is not None:
                data["amount"] = data.get("total_amount")
            elif data.get("total_amount") is None and data.get("amount") is not None:
                data["total_amount"] = data.get("amount")

            # Sincroniza merchant e recipient
            if data.get("recipient") is None and data.get("merchant") is not None:
                data["recipient"] = data.get("merchant")
            elif data.get("merchant") is None and data.get("recipient") is not None:
                data["merchant"] = data.get("recipient")
        return data
