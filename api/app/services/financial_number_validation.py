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


def check_financial_numbers(
    draft: str,
    calculations: list[CalculationResult],
    notes: list[str],
) -> list[ValidationIssue]:
    """Exige cálculo compatível com sinal e unidade; pergunta e RAG não autorizam valores."""
    text = re.sub(r"\[\d+(?:\s*[,-]\s*\d+)*\]", " ", draft)
    metadata = _metadata_spans(text, calculations, notes)
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
            amount = Decimal(canonicalize_number(match["number"]))
            signs = (match["before"] + match["after"]).strip()
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
