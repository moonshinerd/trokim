"""Validação dos números pessoais, independente de agentes e provedores.

Metadados são reconhecidos por posição no texto. Não são apagados: apagar substrings
poderia transformar uma moeda ou um valor inventado em outro valor autorizado.
"""

import re
from decimal import Decimal, InvalidOperation

from app.domain.agents import CalculationResult, IssueSeverity, ValidationIssue
from app.services.number_format import canonicalize_number

_NUMBER = re.compile(
    r"(?<![\w.,])(?P<before>[+−–-]?\s*)"
    r"(?P<currency>R\$|US\$|USD)?\s*(?P<after>[+−–-]?\s*)"
    r"(?P<number>\d+(?:[.,]\d+)*(?:[eE][+-]?\d+)?)"
    r"(?:\s*(?P<unit>%|BRL\b|reais\b|USD\b|meses?\b|mês\b|dias?\b|anos?\b|un\b))?"
    r"(?!\w|[.,]\d)",
    re.I,
)
_DATE_VALUE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")
_YEAR = re.compile(r"(?<!\d)(?:19|20|21)\d{2}(?!\d)")
# O que vem antes de um "-" que é operação, e não sinal: "7.023,92 - 561,78".
_OPERAND_END = re.compile(r"(?:\d|\)|%|\bBRL|\breais)\s*$", re.I)
_UNIT_ALIASES = {"brl": "BRL", "reais": "BRL", "usd": "USD", "mês": "meses", "mes": "meses"}


def _metadata_spans(
    text: str,
    calculations: list[CalculationResult],
    notes: list[str],
) -> list[tuple[int, int]]:
    metadata = list(notes)
    for calc in calculations:
        metadata.extend((calc.label, calc.key, calc.source))
        if isinstance(calc.value, str) and _DATE_VALUE.fullmatch(calc.value):
            metadata.append(calc.value)
    return [
        match.span()
        for literal in metadata
        if literal
        for match in re.finditer(rf"(?<!\w){re.escape(literal)}(?!\w)", text)
    ]


def _unit(match: re.Match[str]) -> str | None:
    currency = (match["currency"] or "").upper()
    currency_unit = ("BRL" if currency == "R$" else "USD") if currency else None
    suffix = (match["unit"] or "").lower()
    suffix_unit = _UNIT_ALIASES.get(suffix, suffix or None)
    if currency_unit and suffix_unit and currency_unit != suffix_unit:
        raise ValueError("Moeda e unidade numérica divergentes.")
    return currency_unit or suffix_unit


def _years(calculations: list[CalculationResult], notes: list[str]) -> set[str]:
    """Anos citados nos rótulos e nas limitações ("setembro de 2026"): podem ser repetidos."""
    texts = [*notes, *(c.label for c in calculations)]
    texts += [c.value for c in calculations if isinstance(c.value, str)]
    return {year for text in texts if text for year in _YEAR.findall(text)}


def _list_marker(text: str, match: re.Match[str]) -> bool:
    """Numeração de lista no início da linha ("1. **Gasto**", "2) Receita"), sem unidade."""
    if match["before"].strip() or match["currency"] or match["unit"]:
        return False
    if len(match["number"]) > 2 or not re.match(r"[.)]\s", text[match.end() : match.end() + 2]):
        return False
    begin = match.start("number")
    line_start = text.rfind("\n", 0, begin) + 1
    return not text[line_start:begin].strip(" \t*#>")


def _sign_is_not_negative(text: str, match: re.Match[str]) -> bool:
    """O "-" antes do número é operação entre valores ou marcador de lista, não sinal."""
    before = match["before"]
    if not before.strip():
        return False
    # O grupo "before" pode começar em quebras de linha anteriores: parte do próprio sinal.
    prefix = text[: match.start("before") + len(before) - len(before.lstrip())]
    line_start = prefix.rfind("\n") + 1
    bullet = not prefix[line_start:].strip() and before.strip() in {"-", "–"} and before[-1:] == " "
    return bullet or bool(_OPERAND_END.search(prefix))


def check_financial_numbers(
    draft: str,
    calculations: list[CalculationResult],
    notes: list[str],
) -> list[ValidationIssue]:
    """Exige cálculo compatível com sinal e unidade; pergunta e RAG não autorizam valores."""
    text = re.sub(r"\[\d+(?:\s*[,-]\s*\d+)*\]", " ", draft)
    metadata = _metadata_spans(text, calculations, notes)
    years = _years(calculations, notes)
    supported: dict[Decimal, set[str | None]] = {}
    for calc in calculations:
        if isinstance(calc.value, str) and _DATE_VALUE.fullmatch(calc.value):
            continue
        try:
            amount = Decimal(str(calc.value))
        except InvalidOperation:
            continue
        if amount.is_finite():
            supported.setdefault(amount, set()).add(calc.unit)

    issues = []
    for match in _NUMBER.finditer(text):
        try:
            unit = _unit(match)
            # Só metadados literais, sem converter datas ou rótulos em dinheiro.
            start = match.start() + len(match.group()) - len(match.group().lstrip())
            if unit not in {"BRL", "USD", "%"} and any(
                a <= start and match.end() <= b for a, b in metadata
            ):
                continue
            # Ano já presente nos rótulos ou limitações, sem moeda nem sinal; numeração de lista.
            if (
                unit is None
                and not (match["before"] + match["after"]).strip()
                and match["number"] in years
            ) or _list_marker(text, match):
                continue
            amount = Decimal(canonicalize_number(match["number"]))
            before = "" if _sign_is_not_negative(text, match) else match["before"]
            signs = (before + match["after"]).strip()
            if sum(char in "+−–-" for char in signs) > 1:
                raise InvalidOperation
            if any(char in signs for char in "−–-"):
                amount = -amount
            valid = (
                amount.is_finite()
                and amount in supported
                and (unit is None or unit in supported[amount])
            )
        except (InvalidOperation, ValueError):
            valid = False
        if not valid:
            issues.append(
                ValidationIssue(
                    code="NUMBER_NOT_SUPPORTED",
                    severity=IssueSeverity.BLOCKER,
                    message=f"Número pessoal sem cálculo compatível: {match.group().strip()}.",
                )
            )
    return issues
