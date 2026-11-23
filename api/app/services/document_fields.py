"""Extração conservadora e fusão comum de campos dos layouts suportados."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.documents import (
    DocumentKind,
    ExtractedField,
    ExtractedTransaction,
    FieldSource,
)

EXPECTED: dict[DocumentKind, set[str]] = {
    DocumentKind.PIX_RECEIPT: {"date", "amount", "counterparty"},
    DocumentKind.BOLETO: {"counterparty", "amount", "due_date"},
    DocumentKind.CARD_INVOICE: {"bank", "due_date", "total"},
}
LABELS = {
    "data": "date",
    "valor": "amount",
    "favorecido": "counterparty",
    "banco": "bank",
    "vencimento": "due_date",
    "total": "total",
}
TEXT_CONFIDENCE = 0.95
VISION_REVIEW_CONFIDENCE = 0.5


def normalized_label(text: str) -> str:
    """Ignora acentos/caixa só em marcadores estruturais; não corrige valores lidos."""
    return " ".join(
        "".join(
            char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
        )
        .casefold()
        .split()
    )


def transaction_parts(raw: str) -> list[str]:
    if "|" in raw:
        return [part.strip() for part in raw.split("|")]
    # O OCR pode omitir separadores verticais; data e moeda continuam inequívocas.
    match = re.fullmatch(
        r"\s*(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(?:R\$\s*)?(-?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})\s*", raw
    )
    return list(match.groups()) if match else []


@dataclass
class FieldCollection:
    """Um campo conflitante nunca pode ser reinserido por outra página ou motor."""

    values: dict[str, ExtractedField] = field(default_factory=dict)
    conflicts: set[str] = field(default_factory=set)

    def merge(self, candidates: list[ExtractedField]) -> None:
        for candidate in candidates:
            key = candidate.key
            if key in self.conflicts:
                continue
            previous = self.values.get(key)
            if previous is not None and previous.value != candidate.value:
                self.values.pop(key)
                self.conflicts.add(key)
            elif previous is None or candidate.confidence > previous.confidence:
                self.values[key] = candidate


@dataclass
class TextExtraction:
    kind: DocumentKind
    fields: list[ExtractedField]
    transactions: list[ExtractedTransaction]

    def sufficient(self, *, continuation: bool = False) -> bool:
        """Continuações bancárias já reconhecidas podem conter só lançamentos."""
        valid_rows = bool(self.transactions) and all(
            row.date is not None and row.amount is not None and row.description
            for row in self.transactions
        )
        if continuation and valid_rows:
            return True
        keys = {item.key for item in self.fields if item.value is not None}
        return (
            self.kind in EXPECTED
            and EXPECTED[self.kind] <= keys
            and (self.kind != DocumentKind.CARD_INVOICE or valid_rows)
        )


def private_text(text: str) -> str:
    """Remove linhas bancárias e identificadores de textos livres, sem log."""
    text = re.sub(r"(?i)\b(?:cpf|cnpj|conta|ag[eê]ncia)\b[^\n]*", "", text)
    text = re.sub(r"\d[\d.\-/]*\d|\d", "", text)
    return " ".join(text.split())


def money(raw: str) -> str | None:
    raw = raw.removeprefix("R$").strip()
    if not re.fullmatch(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}", raw):
        return None
    return str(Decimal(raw.replace(".", "").replace(",", ".")))


def normalized_value(key: str, raw: str, *, canonical: bool = False) -> str | None:
    if key in {"amount", "total"}:
        if canonical and re.fullmatch(r"-?\d+\.\d{2}", raw):
            return str(Decimal(raw))
        return money(raw)
    if key in {"date", "due_date"}:
        try:
            return (
                datetime.strptime(raw, "%Y-%m-%d" if canonical else "%d/%m/%Y").date().isoformat()
            )
        except ValueError:
            return None
    if key in {"counterparty", "bank"}:
        return private_text(raw) or None
    return None


def parse_fields(
    text: str,
    source: FieldSource,
    confidence: float,
) -> tuple[DocumentKind, list[ExtractedField], list[ExtractedTransaction]]:
    lines = text.strip().splitlines()
    title = normalized_label(lines[0]).replace(" ", "") if lines else ""
    kinds = {
        "comprovantepix": DocumentKind.PIX_RECEIPT,
        "boleto": DocumentKind.BOLETO,
        "faturadecartao": DocumentKind.CARD_INVOICE,
    }
    kind = kinds.get(title, DocumentKind.OTHER)
    fields: list[ExtractedField] = []
    transactions: list[ExtractedTransaction] = []
    if kind == DocumentKind.OTHER:
        return kind, fields, transactions
    for line in lines[1:]:
        if ":" not in line:
            continue
        label, raw = line.split(":", 1)
        key = LABELS.get(normalized_label(label))
        if key:
            value = normalized_value(key, raw.strip())
            if value is not None:
                fields.append(
                    ExtractedField(
                        key=key,
                        value=value,
                        confidence=confidence,
                        source=source,
                    )
                )
        elif normalized_label(label) == "lancamento" and kind == DocumentKind.CARD_INVOICE:
            parts = transaction_parts(raw)
            if len(parts) == 3:
                try:
                    day = datetime.strptime(parts[0], "%d/%m/%Y").date()
                except ValueError:
                    day = None
                amount = money(parts[2])
                transactions.append(
                    ExtractedTransaction(
                        date=day,
                        description=private_text(parts[1]),
                        amount=float(Decimal(amount)) if amount else None,
                        confidence=confidence,
                    )
                )
    return kind, fields, transactions


def parse_text(
    text: str,
    source: FieldSource,
    confidence: float,
    *,
    bb_header: str = "",
) -> TextExtraction:
    from app.services.pdf_profiles import is_bb_fatura, parse_bb_fatura

    generic = TextExtraction(*parse_fields(text, source, confidence))
    # Um cabeçalho explícito prevalece sobre o contexto de uma página anterior.
    if generic.kind != DocumentKind.OTHER or not (is_bb_fatura(text) or bb_header):
        return generic
    parsed = parse_bb_fatura(bb_header + text, "documento.pdf")
    fields = [
        ExtractedField(key="bank", value="Banco do Brasil", source=source, confidence=confidence)
    ]
    for key, pattern in (
        ("total", r"Total da Fatura\s+R\$\s*([\d.]+,\d{2})"),
        ("due_date", r"Vencimento\s+(\d{2}/\d{2}/\d{4})"),
    ):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = normalized_value(key, match[1])
            if value is not None:
                fields.append(
                    ExtractedField(
                        key=key,
                        value=value,
                        source=source,
                        confidence=confidence,
                    )
                )
    rows = (
        [
            ExtractedTransaction(
                date=tx.date,
                description=private_text(tx.description),
                amount=tx.amount,
                confidence=confidence,
            )
            for tx in parsed.transactions
        ]
        if parsed
        else []
    )
    return TextExtraction(DocumentKind.CARD_INVOICE, fields, rows)


def bb_continuation_header(text: str) -> str:
    """Reutiliza apenas o cabeçalho efetivamente presente no documento."""
    from app.services.pdf_profiles import is_bb_fatura

    if not is_bb_fatura(text):
        return ""
    marker = re.search(r"SALDO FATURA ANTERIOR[^\n]*", text)
    return text[: marker.end()] + "\n" if marker else ""
