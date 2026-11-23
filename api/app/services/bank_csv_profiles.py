"""Perfis de CSV (ADR 0022). Hoje: fatura do cartão do C6 Bank.

Layout visto em parsers públicos (ver Fontes e Referências), não em arquivo real da equipe:
separador ``;``; colunas Data, Nome no Cartão, Final do Cartão, Categoria, Descrição, Parcela,
Valor (em US$), Cotação (em R$), Valor (em R$). Data ``DD/MM/AAAA`` (da compra); parcela ``Única``
ou ``N/M``; valor positivo é compra e negativo é crédito (pagamento, estorno). O formato numérico
não está confirmado, então aceitamos ``1.234,56`` e ``1234.56``. Cabeçalho que não bate = abstém-se.
"""

import csv
import io
import re
from collections import Counter
from datetime import date

from app.services.bank_pdf_profiles import _make, _result
from app.services.parser_service import OfxParseResult
from app.services.statement_profiles import normalize_text

_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_PARCELA = re.compile(r"^(\d{1,2})\s*/\s*(\d{1,2})$")


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return ""


def _number(raw: str) -> float | None:
    cleaned = re.sub(r"[^\d,.\-]", "", raw or "")
    if not cleaned or cleaned in {"-", ",", "."}:
        return None
    if "," in cleaned:  # formato brasileiro: ponto é milhar, vírgula é decimal
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_c6_fatura_csv(content: bytes, filename: str) -> OfxParseResult | None:
    rows = list(csv.reader(io.StringIO(_decode(content)), delimiter=";"))
    header_at = None
    for i, row in enumerate(rows[:5]):
        names = [normalize_text(c) for c in row]
        if any("final" in n for n in names) and any("parcela" in n for n in names):
            header_at, cols = i, names
            break
    if header_at is None:
        return None

    def col(*needles: str, exclude: str = "") -> int | None:
        for idx, name in enumerate(cols):
            if all(n in name for n in needles) and (not exclude or exclude not in name):
                return idx
        return None

    i_date, i_final = col("data"), col("final")
    i_desc, i_parc = col("descri"), col("parcela")
    i_val = col("valor", "r$", exclude="us$")
    if None in (i_date, i_final, i_desc, i_parc, i_val):
        return None

    txs = []
    finals: Counter[str] = Counter()
    for row in rows[header_at + 1 :]:
        if len(row) <= max(i_date, i_final, i_desc, i_parc, i_val):  # type: ignore[type-var]
            continue
        d = _DATE.match(row[i_date].strip())  # type: ignore[index]
        value = _number(row[i_val])  # type: ignore[index]
        if not d or value is None:
            continue
        try:
            posted = date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        except ValueError:
            continue
        desc = re.sub(r"\s+", " ", row[i_desc]).strip() or "Lançamento"  # type: ignore[index]
        pm = _PARCELA.match(row[i_parc].strip())  # type: ignore[index]
        parcela = None
        if pm and 1 <= int(pm.group(1)) <= int(pm.group(2)):
            parcela = (int(pm.group(1)), int(pm.group(2)))
        finals[re.sub(r"\D", "", row[i_final])] += 1  # type: ignore[index]
        txs.append(
            _make(
                "c6",
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
    final = finals.most_common(1)[0][0] or "cartao"
    dates = [t.date for t in txs]
    return _result("c6", "cartao", f"c6-{final}", txs, min(dates), max(dates), None)
