"""Perfis dos bancos do registro sem perfil próprio (ADR 0022): natureza do lançamento pelo texto.

Servem aos bancos ``experimental``. As regras são as mesmas para todos e ficam em código: a
natureza do lançamento (Pix, pagamento de fatura, tarifa...) decide se ele entra nos totais.
Documento (CPF ou CNPJ) que vier no texto é removido antes de virar descrição.
"""

import re

from app.domain.models import CounterpartyKind, TransactionNature, TransactionType
from app.services.statement_profiles import (
    ParsedMemo,
    StatementKind,
    _clean_merchant,
    guess_counterparty_kind,
    normalize_text,
    strip_documents,
)

_CARD_PAYMENT = re.compile(
    r"\b(pagamento|pagto|pgto|pag)\b.*\b(fatura|cartao)\b|\bfatura\b.*\b(paga|pago|pagamento)\b"
    r"|pagamento recebido|pagamento efetuado",
)
_PIX = re.compile(r"\bpix\b")
_TRANSFER = re.compile(r"\b(ted|doc|tev|transferencia|transf)\b")
_REFUND = re.compile(r"\b(estorno|devolucao|reembolso|cancelamento)\b")
_FEE = re.compile(r"\b(tarifa|anuidade|cesta|pacote|mensalidade|seguro)\b")
_INTEREST = re.compile(r"\b(juros|iof|multa|encargos|mora)\b")
_REDEEM = re.compile(r"\bresgate\b")
_APPLY = re.compile(r"\b(aplicacao|investimento|cdb|rdb|lci|lca|poupanca)\b")
_INCOME = re.compile(r"\brendimentos?\b")


def bank_nature(
    text: str, tx_type: TransactionType, kind: StatementKind | None
) -> TransactionNature:
    """Natureza do lançamento a partir do texto (descrição e tipo) e do sinal."""
    norm = normalize_text(text)
    incoming = tx_type == TransactionType.CREDIT
    if _CARD_PAYMENT.search(norm):
        return TransactionNature.CARD_PAYMENT
    if _REFUND.search(norm):
        return TransactionNature.REFUND
    if _REDEEM.search(norm):
        return TransactionNature.INVESTMENT_REDEEM
    if _APPLY.search(norm) and not incoming:
        return TransactionNature.INVESTMENT_APPLY
    if _INTEREST.search(norm):
        return TransactionNature.INTEREST
    if _FEE.search(norm):
        return TransactionNature.FEE
    if _PIX.search(norm) or _TRANSFER.search(norm):
        return TransactionNature.PIX_IN if incoming else TransactionNature.PIX_OUT
    if incoming:
        return TransactionNature.OTHER
    return TransactionNature.PURCHASE


def _counterparty(text: str) -> str | None:
    cleaned = strip_documents(text)
    if not cleaned:
        return None
    # Tira o rótulo do tipo ("Pix enviado - FULANO" -> "FULANO").
    cleaned = re.sub(
        r"^(pix|ted|doc|transferencia|transf)\w*(\s+(enviad[oa]|recebid[oa]))?\s*[-:]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned or None


class ExperimentalOfxProfile:
    """OFX de bancos sem perfil dedicado: lê NAME e MEMO e classifica pelo texto."""

    name = "experimental"

    @classmethod
    def parse(
        cls,
        memo: str,
        tx_type: TransactionType,
        kind: StatementKind,
        payee: str | None = None,
    ) -> ParsedMemo:
        text = re.sub(r"\s+", " ", " ".join(part for part in (payee, memo) if part)).strip()
        label = strip_documents(text) or text or "Transação sem descrição"
        nature = bank_nature(text, tx_type, kind)
        if nature in {TransactionNature.PIX_IN, TransactionNature.PIX_OUT}:
            who = _counterparty(text)
            return ParsedMemo(
                f"Pix - {who}" if who else label,
                nature,
                merchant=who,
                counterparty_kind=guess_counterparty_kind(who),
            )
        if nature == TransactionNature.PURCHASE:
            store = _clean_merchant(label) or label
            return ParsedMemo(label, nature, merchant=store)
        return ParsedMemo(label, nature)


__all__ = ["CounterpartyKind", "ExperimentalOfxProfile", "bank_nature"]
