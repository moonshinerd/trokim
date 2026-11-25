"""Perfis de PDF dos bancos experimentais (ADR 0022).

Os layouts vêm de documentação e de parsers públicos, não de arquivos reais da equipe; por isso
os bancos saem como ``experimental``. Todos conferem o total do arquivo contra a soma dos
lançamentos quando o PDF traz o total (``reconciled``); sem total, ``reconciled`` fica ``None``.

- Mercado Pago (extrato): data ``DD-MM-AAAA`` numa linha; descrição; ``ID  R$ valor  R$ saldo``.
- Inter (fatura): ``12 de nov. 2026  descrição  R$ 10,00``; ``+`` antes do valor é crédito.
- Itaú (fatura): ``DD/MM  descrição  valor``; ano vem do vencimento; ``-`` é crédito.
- PicPay (extrato): ``DD/MM/AAAA  descrição  R$ valor`` (``-`` é saída); layout genérico.
"""

import re
from datetime import date

from app.domain.models import (
    Transaction,
    TransactionNature,
    TransactionType,
)
from app.services.bank_profiles import bank_nature
from app.services.categorization_service import CategorizationService
from app.services.parser_service import OfxParseResult
from app.services.statement_profiles import OfxMeta, strip_documents

_MONEY = r"-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}"
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    )
}


def _money(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _make(
    bank: str,
    acct: str,
    index: int,
    posted: date,
    description: str,
    value: float,
    outgoing: bool,
    filename: str,
    kind: str,
    parcela: tuple[int, int] | None = None,
) -> Transaction:
    tx_type = TransactionType.DEBIT if outgoing else TransactionType.CREDIT
    label = strip_documents(description) or description
    nature = bank_nature(label, tx_type, None)
    if kind == "cartao" and not outgoing and nature == TransactionNature.OTHER:
        nature = TransactionNature.CARD_PAYMENT
    merchant = label if nature == TransactionNature.PURCHASE else None
    return Transaction(
        id=f"{bank}:{acct}:{index}:{posted.isoformat()}:{value:.2f}",
        account_id=bank,
        description=label,
        amount=round(abs(value), 2),
        date=posted,
        type=tx_type,
        nature=nature,
        merchant=merchant,
        category=CategorizationService.categorize(label, tx_type=tx_type, nature=nature),
        source_file=filename,
        installment_number=parcela[0] if parcela else None,
        installment_total=parcela[1] if parcela else None,
        institution=bank,
    )


def _result(
    bank: str,
    kind: str,
    acct: str,
    txs: list[Transaction],
    start: date | None,
    end: date | None,
    reconciled: bool | None,
    ledger: float | None = None,
    due_date: date | None = None,
) -> OfxParseResult:
    meta = OfxMeta(
        kind=kind,  # type: ignore[arg-type]
        bank_id=None,
        acct_id=acct,
        period_start=start,
        period_end=end,
        generated_at=end,
    )
    return OfxParseResult(
        transactions=txs,
        institution=bank,
        kind=kind,
        ledger_balance=ledger,
        meta=meta,
        reconciled=reconciled,
        due_date=due_date,
    )


# --------------------------------------------------------------------------- Mercado Pago
_MP_DATE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")
_MP_LAST = re.compile(
    rf"^(?P<desc>.*?)\s*(?P<id>\d{{10,}})\s+R\$\s*(?P<v>{_MONEY})\s+R\$\s*(?P<s>{_MONEY})\s*$"
)
_MP_SUMMARY = re.compile(rf"^(saldo inicial|entradas|saidas|saldo final)\D*R\$\s*({_MONEY})", re.I)


def is_mercadopago_extrato(text: str) -> bool:
    low = text.lower()
    return "extrato de conta" in low and "id da opera" in low


def parse_mercadopago_extrato(text: str, filename: str) -> OfxParseResult | None:
    """Extrato de conta do Mercado Pago: uma data por movimento, valor e saldo na última linha."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    txs: list[Transaction] = []
    current: date | None = None
    buffer: list[str] = []
    for ln in lines:
        d = _MP_DATE.match(ln)
        if d:
            current = date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
            buffer = []
            continue
        if current is None:
            continue
        last = _MP_LAST.match(ln)
        if last:
            desc = " ".join([*buffer, last.group("desc")]).strip() or "Movimento"
            value = _money(last.group("v"))
            txs.append(
                _make(
                    "mercadopago",
                    "conta",
                    len(txs),
                    current,
                    desc,
                    value,
                    value < 0,
                    filename,
                    "conta",
                )
            )
            current, buffer = None, []
        else:
            buffer.append(ln)
    if not txs:
        return None
    summary = {
        m.group(1).lower(): _money(m.group(2)) for ln in lines if (m := _MP_SUMMARY.match(ln))
    }
    reconciled = None
    if "saldo inicial" in summary and "saldo final" in summary:
        net = sum(t.amount if t.type == TransactionType.CREDIT else -t.amount for t in txs)
        reconciled = abs(summary["saldo inicial"] + net - summary["saldo final"]) < 0.015
    dates = [t.date for t in txs]
    return _result(
        "mercadopago",
        "conta",
        "conta",
        txs,
        min(dates),
        max(dates),
        reconciled,
        summary.get("saldo final"),
    )


# --------------------------------------------------------------------------- Inter (fatura)
_INTER = re.compile(
    rf"^(?P<d>\d{{1,2}})\s+de\s+(?P<m>[a-zç]{{3,9}})\.?\s+(?P<y>\d{{4}})\s+(?P<desc>.+?)\s+"
    rf"(?P<plus>\+\s*)?R\$\s*(?P<v>{_MONEY})\s*$",
    re.I,
)
_INTER_PARCELA = re.compile(r"\(?parcela\s+(\d{1,2})\s+de\s+(\d{1,2})\)?", re.I)
_INTER_TOTAL = re.compile(rf"total da sua fatura\D*R\$\s*({_MONEY})", re.I)


def is_inter_fatura(text: str) -> bool:
    low = text.lower()
    return "despesas da fatura" in low or "a sua fatura chegou" in low


def parse_inter_fatura(text: str, filename: str) -> OfxParseResult | None:
    txs: list[Transaction] = []
    for ln in (ln.strip() for ln in text.split("\n")):
        m = _INTER.match(ln)
        if not m:
            continue
        month = _MONTHS.get(m.group("m")[:3].lower())
        if not month:
            continue
        desc = m.group("desc")
        parcela = None
        pm = _INTER_PARCELA.search(desc)
        if pm and 1 <= int(pm.group(1)) <= int(pm.group(2)):
            parcela = (int(pm.group(1)), int(pm.group(2)))
            desc = _INTER_PARCELA.sub("", desc).strip()
        posted = date(int(m.group("y")), month, int(m.group("d")))
        txs.append(
            _make(
                "inter",
                "fatura",
                len(txs),
                posted,
                desc,
                _money(m.group("v")),
                outgoing=not m.group("plus"),
                filename=filename,
                kind="cartao",
                parcela=parcela,
            )
        )
    if not txs:
        return None
    total_m = _INTER_TOTAL.search(text)
    reconciled = None
    if total_m:
        spent = sum(t.amount for t in txs if t.type == TransactionType.DEBIT)
        credits = sum(t.amount for t in txs if t.type == TransactionType.CREDIT)
        reconciled = abs(spent - credits - _money(total_m.group(1))) < 0.015
    dates = [t.date for t in txs]
    return _result(
        "inter",
        "cartao",
        "cartao",
        txs,
        min(dates),
        max(dates),
        reconciled,
        -_money(total_m.group(1)) if total_m else None,
    )


# --------------------------------------------------------------------------- Itaú (fatura)
_ITAU = re.compile(rf"^(?P<d>\d{{2}})/(?P<m>\d{{2}})\s+(?P<desc>.+?)\s+(?P<v>{_MONEY})\s*$")
_ITAU_PARCELA = re.compile(r"\b(\d{2})/(\d{2})\b\s*$")
_ITAU_DUE = re.compile(r"(?:vencimento|emiss[aã]o):?\s*(\d{2})/(\d{2})/(\d{4})", re.I)
_ITAU_TOTAL = re.compile(rf"total dos lan[cç]amentos atuais\D*({_MONEY})", re.I)


def is_itau_fatura(text: str) -> bool:
    low = text.lower()
    return "itau" in low.replace("ú", "u") and "lançamentos: compras e saques" in low


def parse_itau_fatura(text: str, filename: str) -> OfxParseResult | None:
    due = _ITAU_DUE.search(text)
    if not due:
        return None
    due_date = date(int(due.group(3)), int(due.group(2)), int(due.group(1)))
    txs: list[Transaction] = []
    started = False
    for ln in (ln.strip() for ln in text.split("\n")):
        low = ln.lower()
        if "lançamentos: compras e saques" in low or "lançamentos: produtos e serviços" in low:
            started = True
            continue
        if "próximas faturas" in low or low.startswith("total dos lançamentos"):
            started = False
            continue
        m = _ITAU.match(ln)
        if not started or not m:
            continue
        month, day = int(m.group("m")), int(m.group("d"))
        year = due_date.year if month <= due_date.month else due_date.year - 1
        try:
            posted = date(year, month, day)
        except ValueError:
            continue
        desc = m.group("desc")
        parcela = None
        pm = _ITAU_PARCELA.search(desc)
        if pm and 1 <= int(pm.group(1)) <= int(pm.group(2)):
            parcela = (int(pm.group(1)), int(pm.group(2)))
            desc = desc[: pm.start()].strip()
        value = _money(m.group("v"))
        txs.append(
            _make(
                "itau",
                "fatura",
                len(txs),
                posted,
                desc,
                value,
                value > 0,
                filename,
                "cartao",
                parcela,
            )
        )
    if not txs:
        return None
    total_m = _ITAU_TOTAL.search(text)
    reconciled = None
    if total_m:
        net = sum(t.amount if t.type == TransactionType.DEBIT else -t.amount for t in txs)
        reconciled = abs(net - _money(total_m.group(1))) < 0.015
    dates = [t.date for t in txs]
    return _result(
        "itau",
        "cartao",
        "cartao",
        txs,
        min(dates),
        due_date,
        reconciled,
        -_money(total_m.group(1)) if total_m else None,
        due_date=due_date,
    )


# --------------------------------------------------------------------------- PicPay (extrato)
_PICPAY = re.compile(
    rf"^(?P<d>\d{{2}})/(?P<m>\d{{2}})/(?P<y>\d{{4}})\s+(?P<desc>.+?)\s+R\$\s*(?P<v>{_MONEY})\s*$"
)


def is_picpay_extrato(text: str) -> bool:
    return (
        "picpay" in text.lower()
        and bool(_PICPAY.search(text.replace("\r", "")))
        or ("picpay" in text.lower() and any(_PICPAY.match(ln.strip()) for ln in text.split("\n")))
    )


def parse_picpay_extrato(text: str, filename: str) -> OfxParseResult | None:
    txs: list[Transaction] = []
    for ln in (ln.strip() for ln in text.split("\n")):
        m = _PICPAY.match(ln)
        if not m:
            continue
        try:
            posted = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
        except ValueError:
            continue
        value = _money(m.group("v"))
        txs.append(
            _make(
                "picpay",
                "conta",
                len(txs),
                posted,
                m.group("desc"),
                value,
                value < 0,
                filename,
                "conta",
            )
        )
    if not txs:
        return None
    dates = [t.date for t in txs]
    return _result("picpay", "conta", "conta", txs, min(dates), max(dates), None)


# --------------------------------------------------------------------------- PicPay (fatura)
_PICPAY_CARD = re.compile(r"picpay\s+card\s+final\s+\d{4}", re.I)
_PICPAY_DUE = re.compile(r"vencimento:?\s*(\d{2})-(\d{2})-(\d{4})", re.I)
_PICPAY_LINE = re.compile(rf"^(?P<d>\d{{2}})/(?P<m>\d{{2}})\s+(?P<desc>.+?)\s+(?P<v>{_MONEY})\s*$")
_PICPAY_PARC = re.compile(r"\bPARC\.?\s*(\d{1,2})/(\d{1,2})\b", re.I)
_PICPAY_SKIP = ("transações nacionais", "data estabelecimento", "subtotal")


def is_picpay_fatura(text: str) -> bool:
    return bool(_PICPAY_CARD.search(text))


def parse_picpay_fatura(text: str, filename: str) -> OfxParseResult | None:
    due = _PICPAY_DUE.search(text)
    if not due:
        return None  # sem o vencimento não há ano seguro para a data DD/MM
    due_date = date(int(due.group(3)), int(due.group(2)), int(due.group(1)))
    txs: list[Transaction] = []
    for ln in (ln.strip() for ln in text.split("\n")):
        if any(skip in ln.lower() for skip in _PICPAY_SKIP):
            continue
        m = _PICPAY_LINE.match(ln)
        if not m:
            continue
        month, day = int(m.group("m")), int(m.group("d"))
        year = due_date.year if month <= due_date.month else due_date.year - 1
        try:
            posted = date(year, month, day)
        except ValueError:
            continue
        desc = m.group("desc")
        parcela = None
        pm = _PICPAY_PARC.search(desc)
        if pm and 1 <= int(pm.group(1)) <= int(pm.group(2)):
            parcela = (int(pm.group(1)), int(pm.group(2)))
            desc = _PICPAY_PARC.sub("", desc).strip()
        value = _money(m.group("v"))
        credit = value < 0 or "pagamento de fatura" in desc.lower()
        txs.append(
            _make(
                "picpay",
                "fatura",
                len(txs),
                posted,
                desc,
                value,
                not credit,
                filename,
                "cartao",
                parcela,
            )
        )
    if not txs:
        return None
    dates = [t.date for t in txs]
    return _result("picpay", "cartao", "cartao", txs, min(dates), due_date, None, due_date=due_date)


PDF_PROFILES = (
    ("mercadopago", is_mercadopago_extrato, parse_mercadopago_extrato),
    ("inter", is_inter_fatura, parse_inter_fatura),
    ("itau", is_itau_fatura, parse_itau_fatura),
    ("picpay", is_picpay_fatura, parse_picpay_fatura),
    ("picpay", is_picpay_extrato, parse_picpay_extrato),
)


def parse_bank_pdf(text: str, filename: str) -> OfxParseResult | None:
    """Primeiro perfil experimental que reconhece o texto e consegue lê-lo."""
    for _bank, matches, parse in PDF_PROFILES:
        if matches(text):
            result = parse(text, filename)
            if result is not None:
                return result
    return None
