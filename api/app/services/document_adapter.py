"""Ponte entre o contrato do agente de documento (#88) e o da validação (#89).

O agente entrega ``app.domain.documents.ExtractedDocument`` (campos por chave e lançamentos);
a validação trabalha com ``app.domain.document.ExtractedDocument`` (campos nomeados e linhas).
Este adaptador converte um no outro sem inventar dado: campo ausente fica ausente.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.domain.document import DocumentType, ExtractedDocument, ExtractedLine
from app.domain.documents import DocumentKind
from app.domain.documents import ExtractedDocument as AgentDocument

_TYPES = {
    DocumentKind.PIX_RECEIPT: DocumentType.PIX,
    DocumentKind.BOLETO: DocumentType.BOLETO,
    DocumentKind.CARD_INVOICE: DocumentType.FATURA,
    DocumentKind.BANK_STATEMENT: DocumentType.OUTRO,
    DocumentKind.OTHER: DocumentType.OUTRO,
}


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def from_agent_document(doc: AgentDocument) -> ExtractedDocument:
    """Converte a saída do agente de documento para a entrada da validação."""
    values = {field.key: field.value for field in doc.fields}
    confidences = [field.confidence for field in doc.fields]
    confidences += [item.confidence for item in doc.transactions]
    amount = values.get("amount")
    total = values.get("total")
    counterparty = values.get("counterparty")
    return ExtractedDocument(
        document_type=_TYPES[doc.kind],
        amount=_decimal(amount) if amount is not None else None,
        # Texto como veio, para a checagem de formato (milhar em inglês) enxergar o original.
        raw_amount=str(amount) if amount is not None else None,
        total_amount=_decimal(total) if total is not None else None,
        date=values.get("date"),
        due_date=values.get("due_date"),
        recipient=str(counterparty) if counterparty is not None else None,
        merchant=str(counterparty) if counterparty is not None else None,
        institution=str(values["bank"]) if values.get("bank") is not None else doc.bank,
        confidence=min(confidences) if confidences else None,
        lines=[
            ExtractedLine(
                description=item.description,
                amount=_decimal(item.amount) if item.amount is not None else Decimal("0.00"),
                date=item.date,
                confidence=item.confidence,
            )
            for item in doc.transactions
        ],
    )
