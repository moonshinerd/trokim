"""Perfis por banco para extratos OFX: detecção, natureza e estabelecimento.

Cada perfil conhece o texto que o banco coloca no campo ``MEMO`` e o converte em
uma descrição limpa, sem dados pessoais da contraparte (CPF, banco, agência,
conta), a natureza do lançamento e o estabelecimento normalizado.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from app.domain.models import CounterpartyKind, TransactionNature, TransactionType

StatementKind = Literal["cartao", "conta"]

_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_CPF_MASCARADO = re.compile(r"[•*\d]{3}\.\d{3}\.\d{3}-[•*\d]{2}|[•*]{3}\.\d{3}\.\d{3}-[•*]{2}")
_PARCELA = re.compile(r"\s*-?\s*Parcela\s+(\d+)\s*/\s*(\d+)\s*$", re.IGNORECASE)
_PARCELA_SIMPLES = re.compile(r"\s*-?\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$")
_PREFIXOS_LOJA = re.compile(
    r"^(?:EBW\s*\*\s*|MP\s*\*\s*|PAG\s*\*\s*|PG\s*\*\s*|IFD\s*\*\s*|Mp\s+)", re.IGNORECASE
)
_SUFIXOS_LOJA = re.compile(r"\s*-\s*NuPay\s*$|\s+NuPay\s*$", re.IGNORECASE)


def normalize_text(value: str) -> str:
    """Minúsculas, sem acento e com espaços colapsados (para comparar textos)."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text).strip().lower()


def decode_ofx(raw: bytes) -> str:
    """Decodifica o OFX tentando UTF-8 antes de cp1252, ignorando o cabeçalho.

    O Nubank declara ``CHARSET:1252`` em faturas cujo conteúdo é UTF-8, o que
    corrompia acentos (``Crédito`` virava ``CrÃ©dito``).
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    # Neutraliza o cabeçalho: o texto já está em str e será reenviado em UTF-8.
    text = re.sub(r"ENCODING:\S+", "ENCODING:UTF-8", text, count=1)
    return re.sub(r"CHARSET:\S+", "CHARSET:NONE", text, count=1)


@dataclass(frozen=True)
class Detection:
    institution: str
    kind: StatementKind


def detect_statement(text: str) -> Detection | None:
    """Reconhece banco e tipo (cartão ou conta) pelo conteúdo do OFX."""
    upper = text.upper()
    kind: StatementKind
    if "<CCSTMTRS>" in upper or "<CREDITCARDMSGSRSV1>" in upper:
        kind = "cartao"
    elif "<STMTRS>" in upper or "<BANKMSGSRSV1>" in upper:
        kind = "conta"
    else:
        return None
    org = re.search(r"<ORG>([^<\r\n]*)", text)
    fid = re.search(r"<FID>([^<\r\n]*)", text)
    bank_id = re.search(r"<BANKID>([^<\r\n]*)", text)
    org_text = normalize_text(org.group(1)) if org else ""
    codes = {fid.group(1).strip() if fid else "", bank_id.group(1).strip() if bank_id else ""}
    if "nu pagamentos" in org_text or "nubank" in org_text or codes & {"260", "0260"}:
        return Detection("nubank", kind)
    return None


@dataclass(frozen=True)
class ParsedMemo:
    description: str
    nature: TransactionNature
    merchant: str | None = None
    counterparty_kind: CounterpartyKind | None = None
    installment_number: int | None = None
    installment_total: int | None = None


def _clean_merchant(raw: str) -> str:
    name = _PREFIXOS_LOJA.sub("", raw.strip())
    name = _SUFIXOS_LOJA.sub("", name)
    return re.sub(r"\s+", " ", name).strip(" -*")


def _split_parcela(text: str) -> tuple[str, int | None, int | None]:
    match = _PARCELA.search(text)
    if match:
        return text[: match.start()].strip(), int(match.group(1)), int(match.group(2))
    return text, None, None


def _counterparty(parts: list[str]) -> tuple[str | None, CounterpartyKind | None]:
    """Nome e tipo da contraparte de um Pix; descarta documento, banco e conta."""
    if not parts:
        return None, None
    name = re.sub(r"\s*\([^)]*\)\s*$", "", parts[0]).strip()
    rest = " ".join(parts[1:])
    kind = None
    if _CNPJ.search(rest):
        kind = CounterpartyKind.COMPANY
    elif _CPF_MASCARADO.search(rest):
        kind = CounterpartyKind.PERSON
    return (name or None), kind


class NubankProfile:
    """Textos de ``MEMO`` do Nubank (conta e cartão)."""

    name = "nubank"

    @classmethod
    def parse(cls, memo: str, tx_type: TransactionType, kind: StatementKind) -> ParsedMemo:
        text = re.sub(r"\s+", " ", memo or "").strip()
        norm = normalize_text(text)
        parts = [p.strip() for p in text.split(" - ")]
        head = normalize_text(parts[0])

        if kind == "cartao" and norm.startswith("pagamento recebido"):
            return ParsedMemo("Pagamento da fatura", TransactionNature.CARD_PAYMENT)
        if tx_type == TransactionType.CREDIT and "estorno" in norm:
            store_raw, _, _ = _split_parcela(re.sub(r"\s*-?\s*estorno.*$", "", text, flags=re.I))
            store = _clean_merchant(store_raw)
            return ParsedMemo(
                f"Estorno - {store}" if store else "Estorno",
                TransactionNature.REFUND,
                store or None,
            )
        if head.startswith("estorno") or head.startswith("reembolso"):
            who, who_kind = _counterparty(parts[1:])
            label = parts[0] + (f" - {who}" if who else "")
            return ParsedMemo(label, TransactionNature.REFUND, who, who_kind)

        if head.startswith("pagamento de fatura"):
            return ParsedMemo("Pagamento da fatura", TransactionNature.CARD_PAYMENT)
        if head.startswith("dinheiro guardado") or head.startswith("aplicacao"):
            return ParsedMemo(parts[0], TransactionNature.INVESTMENT_APPLY)
        if head.startswith("resgate rdb") or head.startswith("resgate planejado"):
            return ParsedMemo(parts[0], TransactionNature.INVESTMENT_REDEEM)
        if "resgate" in head and "emprestimo" not in head:
            return ParsedMemo(parts[0], TransactionNature.INVESTMENT_REDEEM)
        if head.startswith("valor adicionado na conta"):
            return ParsedMemo(parts[0], TransactionNature.INTERNAL_TRANSFER)

        if head.startswith("transferencia enviada pelo pix"):
            who, who_kind = _counterparty(parts[1:])
            label = "Pix enviado" + (f" - {who}" if who else "")
            return ParsedMemo(label, TransactionNature.PIX_OUT, who, who_kind)
        if head.startswith("transferencia recebida pelo pix") or head.startswith(
            "transferencia recebida"
        ):
            who, who_kind = _counterparty(parts[1:])
            label = "Pix recebido" + (f" - {who}" if who else "")
            return ParsedMemo(label, TransactionNature.PIX_IN, who, who_kind)

        if head.startswith("compra no debito") or head.startswith("pix no credito"):
            store_raw = " - ".join(parts[1:]) if len(parts) > 1 else parts[0]
            store_raw, number, total = _split_parcela(store_raw)
            store = _clean_merchant(store_raw)
            prefix = "Pix no crédito" if head.startswith("pix no credito") else "Compra no débito"
            return ParsedMemo(
                f"{prefix} - {store}" if store else prefix,
                TransactionNature.PURCHASE,
                store or None,
                None,
                number,
                total,
            )

        if re.match(r"(juros|multa|encargos|iof)\b", head):
            return ParsedMemo(text, TransactionNature.INTEREST)
        if head.startswith("tarifa") or head.startswith("anuidade"):
            return ParsedMemo(text, TransactionNature.FEE)

        # Cartão: qualquer outro débito é compra; crédito desconhecido fica como "outro".
        if kind == "cartao" and tx_type == TransactionType.DEBIT:
            store_raw, number, total = _split_parcela(text)
            store = _clean_merchant(store_raw)
            return ParsedMemo(
                store or text, TransactionNature.PURCHASE, store or None, None, number, total
            )
        return ParsedMemo(text or "Transação sem descrição", TransactionNature.OTHER)


PROFILES = {"nubank": NubankProfile}
