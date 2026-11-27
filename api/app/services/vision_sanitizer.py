"""Proteção dos pixels antes da visão (ADR 0021): tarja CPF, CNPJ, agência e conta.

Usa as caixas que o OCR local já leu na mesma página, então a imagem não é lida duas vezes.
Sem caixas (OCR vazio ou sem posição), devolve ``None`` e a visão fica bloqueada: na dúvida,
a imagem não sai do aparelho.
"""

from __future__ import annotations

import io
import re

from PIL import Image, ImageDraw

from app.models.vision_provider import OcrWord
from app.services.statement_profiles import normalize_text

# Documento de pessoa ou empresa, com ou sem pontuação, inclusive mascarado pelo banco.
_DOCUMENT = re.compile(
    r"(?<!\d)(?:\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"  # CNPJ
    r"|[\d•*xX]{3}\.?\d{3}\.?\d{3}-?[\d•*xX]{2})(?!\d)"  # CPF, inteiro ou mascarado
)
# Rótulo seguido do número na mesma caixa: "Agência: 1234", "Conta 56789-0", "CPF ***.123".
_LABEL_WITH_VALUE = re.compile(r"\b(?:ag(?:encia)?|conta(?: corrente)?|c/c|cpf|cnpj)\b\W*[\d•*]")
# Rótulo sozinho na caixa: o número vem na caixa seguinte da mesma linha.
_LABEL_ONLY = re.compile(r"^\W*(?:ag(?:encia)?|conta(?: corrente)?|c/c|cpf|cnpj)\W*$")
# Número de conta com dígito verificador ("12345-6") ou agência de 4 dígitos com DV.
_ACCOUNT = re.compile(r"(?<![\d,./])\d{4,12}-[\dxX](?![\d,])")
_MARGIN = 3


def _sensitive(word: OcrWord) -> bool:
    text = normalize_text(word.text)
    return bool(
        _DOCUMENT.search(word.text) or _LABEL_WITH_VALUE.search(text) or _ACCOUNT.search(text)
    )


def _next_on_line(label: OcrWord, words: list[OcrWord]) -> OcrWord | None:
    """A caixa mais próxima à direita do rótulo, na mesma linha (alturas que se sobrepõem)."""
    assert label.box is not None
    x0, y0, x1, y1 = label.box
    candidates = [
        w
        for w in words
        if w.box is not None
        and w is not label
        and w.box[0] >= x1 - _MARGIN
        and min(y1, w.box[3]) - max(y0, w.box[1]) > 0
    ]
    return min(candidates, key=lambda w: w.box[0], default=None)  # type: ignore[index]


def sensitive_boxes(words: list[OcrWord]) -> list[tuple[int, int, int, int]]:
    """Caixas a tarjar: documento, conta e agência, e o valor ao lado de um rótulo sozinho."""
    positioned = [w for w in words if w.box is not None]
    boxes = []
    for word in positioned:
        if _sensitive(word):
            boxes.append(word.box)
        elif _LABEL_ONLY.match(normalize_text(word.text)):
            boxes.append(word.box)
            value = _next_on_line(word, positioned)
            if value is not None:
                boxes.append(value.box)
    return boxes  # type: ignore[return-value]


class OcrMaskingSanitizer:
    """Tarja os trechos sensíveis lidos pelo OCR e devolve a imagem em PNG."""

    def sanitize(self, image: bytes, words: list[OcrWord] | None = None) -> bytes | None:
        if not words or not any(w.box is not None for w in words):
            return None
        try:
            with Image.open(io.BytesIO(image)) as opened:
                canvas = opened.convert("RGB")
        except OSError:
            return None
        draw = ImageDraw.Draw(canvas)
        for x0, y0, x1, y1 in sensitive_boxes(words):
            draw.rectangle((x0 - _MARGIN, y0 - _MARGIN, x1 + _MARGIN, y1 + _MARGIN), fill=(0, 0, 0))
        out = io.BytesIO()
        canvas.save(out, format="PNG")
        return out.getvalue()
