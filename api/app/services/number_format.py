"""Normalização numérica compartilhada pelas políticas de validação."""

import re
from decimal import Decimal, InvalidOperation


def canonicalize_number(raw: str) -> str:
    """Converte representações numéricas pt-BR e internacionais para forma decimal canônica.

    Exemplos:
    - "1.234,56" -> "1234.56"
    - "0,20" -> "0.2"
    - "12,5" -> "12.5"
    - "30" -> "30"
    """
    cleaned = raw.strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        dec = Decimal(cleaned).normalize()
        s = format(dec, "f")
        return s.rstrip("0").rstrip(".") if "." in s else s
    except (InvalidOperation, ValueError):
        return cleaned
