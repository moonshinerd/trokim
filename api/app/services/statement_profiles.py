"""Perfis por banco para extratos OFX: detecção, natureza e estabelecimento.

Cada perfil conhece o texto que o banco coloca no campo ``MEMO`` e o converte em
uma descrição limpa, sem dados pessoais da contraparte (CPF, banco, agência,
conta), a natureza do lançamento e o estabelecimento normalizado.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.domain.models import CounterpartyKind, TransactionNature, TransactionType

StatementKind = Literal["cartao", "conta"]

_CONTA_DESTINO = re.compile(
    r"\((\d{4})\)\s*Ag[êe]ncia:\s*\d+\s*Conta:\s*([\d.]+-?\d?)", re.IGNORECASE
)
_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_CPF_MASCARADO = re.compile(r"[•*\d]{3}\.\d{3}\.\d{3}-[•*\d]{2}|[•*]{3}\.\d{3}\.\d{3}-[•*]{2}")
_PARCELA = re.compile(r"\s*-?\s*Parcela\s+(\d+)\s*/\s*(\d+)\s*$", re.IGNORECASE)
_PARCELA_SIMPLES = re.compile(r"\s*-?\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$")
_PREFIXOS_LOJA = re.compile(
    r"^(?:EBW\s*\*\s*|MP\s*\*\s*|PAG\s*\*\s*|PG\s*\*\s*|IFD\s*\*\s*|Mp\s+)", re.IGNORECASE
)
_NUMERO_LOJA = re.compile(r"\s+\d{1,6}$")
_SUFIXOS_LOJA = re.compile(r"\s*-\s*NuPay\s*$|\s+NuPay\s*$", re.IGNORECASE)


def normalize_doc(raw: str | None) -> str | None:
    """CNPJ vira só dígitos (formatado ou não); CPF mascarado fica como está.

    Assim o CNPJ de um Pix do Nubank ("11.111.111/0001-11") é o mesmo do extrato do BB
    ("11111111000111").
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 14:
        return digits
    if "•" in raw or "*" in raw:
        return raw.strip()
    return digits or None


def doc_is_company(doc: str | None) -> bool:
    return bool(doc) and len(re.sub(r"\D", "", doc or "")) == 14


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
    if "banco do brasil" in org_text or codes & {"1", "001", "0001"}:
        return Detection("bb", kind)
    return None


@dataclass(frozen=True)
class OfxMeta:
    """Metadados do arquivo: conta, período e quando foi gerado."""

    kind: StatementKind | None
    bank_id: str | None
    acct_id: str | None
    period_start: date | None
    period_end: date | None
    generated_at: date | None


def _first_date(text: str, tag: str) -> date | None:
    match = re.search(rf"<{tag}>\s*(\d{{8}})", text)
    if not match:
        return None
    raw = match.group(1)
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return None


def parse_ofx_meta(text: str) -> OfxMeta:
    """Lê tipo, conta e período do OFX, mesmo de bancos sem perfil."""
    upper = text.upper()
    kind: StatementKind | None = None
    if "<CCSTMTRS>" in upper or "<CREDITCARDMSGSRSV1>" in upper:
        kind = "cartao"
    elif "<STMTRS>" in upper or "<BANKMSGSRSV1>" in upper:
        kind = "conta"
    acct = re.search(r"<ACCTID>([^<\r\n]*)", text)
    bank = re.search(r"<BANKID>([^<\r\n]*)", text) or re.search(r"<FID>([^<\r\n]*)", text)
    return OfxMeta(
        kind=kind,
        bank_id=bank.group(1).strip() if bank else None,
        acct_id=acct.group(1).strip() if acct else None,
        period_start=_first_date(text, "DTSTART"),
        period_end=_first_date(text, "DTEND"),
        generated_at=_first_date(text, "DTSERVER"),
    )


@dataclass(frozen=True)
class ParsedMemo:
    description: str
    nature: TransactionNature
    merchant: str | None = None
    counterparty_kind: CounterpartyKind | None = None
    counterparty_doc: str | None = None
    counterparty_account: str | None = None
    installment_number: int | None = None
    installment_total: int | None = None


def _clean_merchant(raw: str) -> str:
    name = _PREFIXOS_LOJA.sub("", raw.strip())
    name = _SUFIXOS_LOJA.sub("", name)
    name = _NUMERO_LOJA.sub("", name)  # "DROGASIL 123" -> "DROGASIL"
    return re.sub(r"\s+", " ", name).strip(" -*")


def _split_parcela(text: str) -> tuple[str, int | None, int | None]:
    match = _PARCELA.search(text)
    if match:
        return text[: match.start()].strip(), int(match.group(1)), int(match.group(2))
    return text, None, None


def _counterparty(
    parts: list[str],
) -> tuple[str | None, CounterpartyKind | None, str | None, str | None]:
    """Nome, tipo, documento e conta da contraparte de um Pix; banco e conta são descartados.

    O documento (CNPJ ou CPF mascarado) só é guardado internamente, para reconhecer as
    próprias contas do usuário; ele nunca é exposto.
    """
    if not parts:
        return None, None, None, None
    name = re.sub(r"\s*\([^)]*\)\s*$", "", parts[0]).strip()
    rest = " ".join(parts[1:])
    kind = None
    doc = None
    cnpj = _CNPJ.search(rest)
    cpf = _CPF_MASCARADO.search(rest)
    if cnpj:
        kind, doc = CounterpartyKind.COMPANY, normalize_doc(cnpj.group(0))
    elif cpf:
        kind, doc = CounterpartyKind.PERSON, normalize_doc(cpf.group(0))
    account = None
    destino = _CONTA_DESTINO.search(rest)
    if destino:
        digits = re.sub(r"\D", "", destino.group(2))
        if digits:
            account = f"{destino.group(1)}:{digits}"
    return (name or None), kind, doc, account


class NubankProfile:
    """Textos de ``MEMO`` do Nubank (conta e cartão)."""

    name = "nubank"

    @classmethod
    def parse(
        cls,
        memo: str,
        tx_type: TransactionType,
        kind: StatementKind,
        payee: str | None = None,
    ) -> ParsedMemo:
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
            who, who_kind, who_doc, who_acct = _counterparty(parts[1:])
            label = parts[0] + (f" - {who}" if who else "")
            return ParsedMemo(label, TransactionNature.REFUND, who, who_kind, who_doc, who_acct)

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
            who, who_kind, who_doc, who_acct = _counterparty(parts[1:])
            label = "Pix enviado" + (f" - {who}" if who else "")
            return ParsedMemo(label, TransactionNature.PIX_OUT, who, who_kind, who_doc, who_acct)
        if head.startswith("transferencia recebida pelo pix") or head.startswith(
            "transferencia recebida"
        ):
            who, who_kind, who_doc, who_acct = _counterparty(parts[1:])
            label = "Pix recebido" + (f" - {who}" if who else "")
            return ParsedMemo(label, TransactionNature.PIX_IN, who, who_kind, who_doc, who_acct)

        if head.startswith("compra no debito") or head.startswith("pix no credito"):
            store_raw = " - ".join(parts[1:]) if len(parts) > 1 else parts[0]
            store_raw, number, total = _split_parcela(store_raw)
            store = _clean_merchant(store_raw)
            prefix = "Pix no crédito" if head.startswith("pix no credito") else "Compra no débito"
            return ParsedMemo(
                f"{prefix} - {store}" if store else prefix,
                TransactionNature.PURCHASE,
                merchant=store or None,
                installment_number=number,
                installment_total=total,
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
                store or text,
                TransactionNature.PURCHASE,
                merchant=store or None,
                installment_number=number,
                installment_total=total,
            )
        return ParsedMemo(text or "Transação sem descrição", TransactionNature.OTHER)


_BB_MEMO = re.compile(
    r"^(?P<bank>\d{1,4})\s+(?P<branch>\d{3,5})\s+(?P<doc>\d{11}|\d{14})\s+(?P<name>.+)$"
)


class BancoDoBrasilProfile:
    """Conta corrente do Banco do Brasil (OFX "Money 2000+").

    O ``NAME`` traz o tipo ("TED-Crédito em Conta", "Pix - Recebido"...) e o ``MEMO`` traz,
    quando há contraparte, o banco, a agência, o documento (CPF ou CNPJ **sem máscara**) e o
    nome. O documento só é guardado internamente; nunca sai pela API.
    """

    name = "bb"

    @classmethod
    def parse(
        cls,
        memo: str,
        tx_type: TransactionType,
        kind: StatementKind,
        payee: str | None = None,
    ) -> ParsedMemo:
        kind_text = re.sub(r"\s+", " ", payee or "").strip()
        norm = normalize_text(kind_text)
        memo_text = re.sub(r"\s+", " ", memo or "").strip()
        counterparty = _BB_MEMO.match(memo_text)
        who = doc = None
        who_kind = None
        if counterparty:
            who = counterparty.group("name").strip()
            doc = normalize_doc(counterparty.group("doc"))
            who_kind = CounterpartyKind.COMPANY if doc_is_company(doc) else CounterpartyKind.PERSON
        incoming = tx_type == TransactionType.CREDIT

        def transfer(prefix: str) -> ParsedMemo:
            nature = TransactionNature.PIX_IN if incoming else TransactionNature.PIX_OUT
            label = prefix + (f" - {who}" if who else "")
            return ParsedMemo(label, nature, who, who_kind, doc)

        if "fatura" in norm or "ourocard" in norm or "cartao" in norm and "pag" in norm:
            return ParsedMemo("Pagamento da fatura", TransactionNature.CARD_PAYMENT)
        if norm.startswith(("ted", "doc", "pix", "transferencia", "tev")):
            return transfer("Pix" if norm.startswith("pix") else "Transferência")
        if "resgate" in norm:
            return ParsedMemo(kind_text, TransactionNature.INVESTMENT_REDEEM)
        if norm.startswith(("aplicacao", "bb rende", "investimento")):
            return ParsedMemo(kind_text, TransactionNature.INVESTMENT_APPLY)
        if re.match(r"(juros|iof|multa|encargos)\b", norm):
            return ParsedMemo(kind_text or memo_text, TransactionNature.INTEREST)
        if norm.startswith(("tarifa", "cesta", "pacote", "anuidade")):
            return ParsedMemo(kind_text or memo_text, TransactionNature.FEE)
        if norm.startswith(("compra", "pagto", "pagamento", "debito", "saque")):
            store = who or memo_text or kind_text
            return ParsedMemo(
                f"{kind_text} - {store}" if store and store != kind_text else kind_text,
                TransactionNature.PURCHASE if not incoming else TransactionNature.OTHER,
                merchant=store or None,
                counterparty_kind=who_kind,
                counterparty_doc=doc,
            )
        text = kind_text or memo_text or "Transação sem descrição"
        return ParsedMemo(
            text,
            TransactionNature.OTHER,
            merchant=who,
            counterparty_kind=who_kind,
            counterparty_doc=doc,
        )


PROFILES = {"nubank": NubankProfile, "bb": BancoDoBrasilProfile}
