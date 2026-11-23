"""Perfis de fatura em PDF (hoje: Banco do Brasil, cartão Ourocard).

O PDF do BB tem regras próprias, diferentes das do Nubank:

- valor **positivo** é compra e **negativo** é crédito (pagamento da fatura, estorno);
- o cabeçalho traz "Fatura fechada em", o vencimento, o total e o final do cartão;
- a data do lançamento é só ``DD/MM`` (o ano vem da data de fechamento);
- parcelas aparecem na descrição como ``PARC NN/MM``;
- as seções (Pagamentos/Créditos, Serviços, Compras, Compras parceladas) separam os lançamentos.

O arquivo do banco só é lido localmente; nada é enviado para fora.
"""

import io
import re
from datetime import date, timedelta

from pypdf import PdfReader

from app.domain.models import (
    Transaction,
    TransactionCategory,
    TransactionNature,
    TransactionType,
)
from app.services.categorization_service import CategorizationService
from app.services.parser_service import OfxParseResult
from app.services.statement_profiles import OfxMeta, _clean_merchant

_LINE = re.compile(
    r"^(?P<d>\d{2}/\d{2})\s+(?P<desc>.+?)\s+(?P<country>[A-Z]{2})\s+"
    r"(?:[A-Z]{3}\s+-?[\d.,]+\s+)?R\$\s*(?P<val>-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})\s*$"
)
_PARCELA = re.compile(r"\bPARC\.?\s*(\d{1,2})\s*/\s*(\d{1,2})\b", re.IGNORECASE)
# Cabeçalhos de categoria do próprio BB (ex.: "Restaurantes"). Servem de dica quando o
# dicionário do Trokim não conhece o estabelecimento.
_BB_CATEGORIES = {
    "restaurantes": TransactionCategory.FOOD,
    "supermercados": TransactionCategory.FOOD,
    "alimentação": TransactionCategory.FOOD,
    "alimentacao": TransactionCategory.FOOD,
    "lazer": TransactionCategory.LEISURE,
    "entretenimento": TransactionCategory.LEISURE,
    "viagens": TransactionCategory.LEISURE,
    "turismo": TransactionCategory.LEISURE,
    "serviços": TransactionCategory.SERVICES,
    "servicos": TransactionCategory.SERVICES,
    "saúde": TransactionCategory.HEALTH,
    "saude": TransactionCategory.HEALTH,
    "farmácias": TransactionCategory.HEALTH,
    "transporte": TransactionCategory.TRANSPORT,
    "combustíveis": TransactionCategory.TRANSPORT,
    "educação": TransactionCategory.EDUCATION,
    "educacao": TransactionCategory.EDUCATION,
}
_NOT_HEADING = ("data ", "total", "página", "fale", "saldo", "lançamentos", "confira", "para ")
_FEE_WORDS = re.compile(r"anuidade|tarifa|seguro|encargos|\biof\b|juros|multa", re.IGNORECASE)


def _money(raw: str) -> float:
    cleaned = raw.replace(".", "").replace(",", ".")
    return float(cleaned)


def _br_date(raw: str) -> date | None:
    try:
        day, month, year = (int(p) for p in raw.split("/"))
        return date(year, month, day)
    except ValueError:
        return None


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    last = (date(year + (month + 1) // 12, (month + 1) % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month + 1, min(day.day, last))


def _pdf_creation_date(reader: PdfReader) -> date | None:
    raw = str((reader.metadata or {}).get("/CreationDate") or "")
    match = re.search(r"(\d{4})(\d{2})(\d{2})", raw)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _category(
    merchant: str, tx_type: TransactionType, nature: TransactionNature, heading: str
) -> TransactionCategory:
    category = CategorizationService.categorize(merchant, tx_type=tx_type, nature=nature)
    if category == TransactionCategory.OTHER and nature == TransactionNature.PURCHASE:
        return _BB_CATEGORIES.get(heading, TransactionCategory.OTHER)
    return category


def is_bb_fatura(text: str) -> bool:
    low = text.lower()
    return "bb.com.br" in low and ("fatura fechada em" in low or "ourocard" in low)


def parse_bb_fatura(
    text: str, filename: str, generated_at: date | None = None
) -> OfxParseResult | None:
    """Lê a fatura do cartão Ourocard (texto já extraído do PDF)."""
    closing_match = re.search(r"Fatura fechada em\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    closing = _br_date(closing_match.group(1)) if closing_match else None
    final = re.search(r"ourocard[^\n]*Final\s+(\d{4})", text, re.IGNORECASE) or re.search(
        r"\(Cart[aã]o\s+(\d{4})\)", text, re.IGNORECASE
    )
    if closing is None or final is None:
        return None
    total_match = re.search(r"Total da Fatura\s+R\$\s*([\d.]+,\d{2})", text, re.IGNORECASE)
    total = _money(total_match.group(1)) if total_match else None
    period_end = closing
    period_start = _add_months(closing, -1) + timedelta(days=1)
    # "Fatura fechada em" é explícito: o PDF não pode ter sido gerado antes do fechamento
    # (a data de criação do arquivo às vezes vem errada).
    earliest = closing + timedelta(days=1)
    generated = max(generated_at, earliest) if generated_at else earliest

    previous = re.search(r"SALDO FATURA ANTERIOR\s+BR\s+R\$\s*([\d.]+,\d{2})", text)
    previous_balance = _money(previous.group(1)) if previous else None

    transactions: list[Transaction] = []
    heading = ""
    started = False
    ended = False
    for index, raw in enumerate(text.split("\n")):
        line = raw.strip()
        if not line or ended:
            continue
        key = line.lower()
        if key.startswith("total da fatura"):
            ended = True
            continue
        if key.startswith("saldo fatura anterior"):
            started = True
            continue
        if not started:
            continue
        match = _LINE.match(line)
        if not match:
            words = line.split()
            if (
                1 <= len(words) <= 3
                and not any(ch.isdigit() for ch in line)
                and not key.startswith(_NOT_HEADING)
            ):
                heading = key
            continue
        try:
            value = _money(match.group("val").lstrip("-"))
        except ValueError:
            continue
        negative = match.group("val").startswith("-")
        day, month = (int(p) for p in match.group("d").split("/"))
        year = closing.year if month <= closing.month else closing.year - 1
        try:
            posted = date(year, month, day)
        except ValueError:
            continue
        # O BB separa o estabelecimento da cidade por vários espaços.
        description = re.split(r"\s{2,}", match.group("desc").strip())[0]
        description = re.sub(r"\s+", " ", description).strip()
        number = total_parcels = None
        parcela = _PARCELA.search(description)
        if parcela and 1 <= int(parcela.group(1)) <= int(parcela.group(2)):
            number, total_parcels = int(parcela.group(1)), int(parcela.group(2))
            # Depois de "PARC NN/MM" só sobra a cidade.
            description = description[: parcela.start()].strip()
        merchant = _clean_merchant(re.sub(r"\s+", " ", description)) or description
        low = description.lower()
        if negative:
            tx_type = TransactionType.CREDIT
            nature = (
                TransactionNature.REFUND
                if "estorno" in low or "cancel" in low
                else TransactionNature.CARD_PAYMENT
            )
        else:
            tx_type = TransactionType.DEBIT
            nature = (
                TransactionNature.FEE if _FEE_WORDS.search(merchant) else TransactionNature.PURCHASE
            )
        transactions.append(
            Transaction(
                id=f"bb:{final.group(1)}:{index}:{posted.isoformat()}:{value:.2f}",
                account_id="bb",
                description=merchant,
                amount=round(value, 2),
                date=posted,
                type=tx_type,
                nature=nature,
                merchant=merchant
                if nature in {TransactionNature.PURCHASE, TransactionNature.REFUND}
                else None,
                category=_category(merchant, tx_type, nature, heading),
                source_file=filename,
                installment_number=number,
                installment_total=total_parcels,
                institution="bb",
            )
        )

    if total is not None and previous_balance is not None:
        debits = sum(t.amount for t in transactions if t.type == TransactionType.DEBIT)
        credits = sum(t.amount for t in transactions if t.type == TransactionType.CREDIT)
        reconciled = abs((previous_balance + debits - credits) - total) < 0.015
    else:
        reconciled = None

    meta = OfxMeta(
        kind="cartao",
        bank_id="0001",
        acct_id=f"ourocard-{final.group(1)}",
        period_start=period_start,
        period_end=period_end,
        generated_at=generated,
    )
    return OfxParseResult(
        transactions=transactions,
        institution="bb",
        kind="cartao",
        ledger_balance=-total if total is not None else None,
        meta=meta,
        reconciled=reconciled,
    )


def parse_pdf_statement(content: bytes, filename: str) -> OfxParseResult | None:
    """Tenta um perfil conhecido de PDF. ``None`` quando o PDF não é de nenhum perfil."""
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if is_bb_fatura(text):
        return parse_bb_fatura(text, filename, _pdf_creation_date(reader))
    from app.services.bank_pdf_profiles import parse_bank_pdf  # perfis experimentais

    return parse_bank_pdf(text, filename)


__all__ = ["is_bb_fatura", "parse_bb_fatura", "parse_pdf_statement"]
