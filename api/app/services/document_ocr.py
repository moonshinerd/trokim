"""Reconstrói linhas e confianças usando o contrato de OCR da ADR 0021."""

from app.models.vision_provider import OcrResult, OcrWord
from app.services.document_fields import LABELS
from app.services.document_reading import DocumentReadError


def ocr_lines(reading: OcrResult) -> list[tuple[str, float]]:
    """Agrupa palavras por sobreposição vertical; sem caixas, preserva a ordem."""
    if not isinstance(reading, OcrResult) or not all(
        0 <= word.confidence <= 1 for word in reading.words
    ):
        raise DocumentReadError("INVALID_OCR_RESULT")
    if not reading.words or any(word.box is None for word in reading.words):
        return [
            (line, word.confidence)
            for word in reading.words
            for line in word.text.splitlines()
            if line.strip()
        ]
    groups: list[list[OcrWord]] = []
    for word in sorted(reading.words, key=lambda word: (word.box[1], word.box[0])):
        box = word.box
        for group in groups:
            reference = group[0].box
            overlap = min(box[3], reference[3]) - max(box[1], reference[1])
            if overlap > 0 and overlap >= 0.5 * min(box[3] - box[1], reference[3] - reference[1]):
                group.append(word)
                break
        else:
            groups.append([word])
    return [
        (
            " ".join(word.text for word in sorted(group, key=lambda word: word.box[0])),
            min(word.confidence for word in group),
        )
        for group in groups
    ]


def ocr_text_and_confidence(reading: OcrResult) -> tuple[str, dict[str, float]]:
    lines = ocr_lines(reading)
    confidences: dict[str, float] = {}
    for text, confidence in lines:
        label = text.split(":", 1)[0].strip().casefold()
        key = LABELS.get(label)
        if key:
            confidences[key] = min(confidences.get(key, 1.0), confidence)
    return "\n".join(text for text, _ in lines), confidences


def ocr_row_confidences(reading: OcrResult, count: int) -> list[float]:
    """Confiança da linha de lançamento, sem promovê-la pela média do documento."""
    import re

    values = [
        confidence
        for text, confidence in ocr_lines(reading)
        if (
            text.strip().casefold().startswith("lançamento:")
            and len(text.split(":", 1)[1].split("|")) == 3
        )
        or re.match(r"^\d{2}/\d{2}\s+.+\s+[A-Z]{2}\s+.*R\$\s*-?[\d.,]+\s*$", text)
    ]
    if len(values) != count:
        # Sem associação exata, não atribui certeza por posição ou por média.
        return [min((word.confidence for word in reading.words), default=0.0)] * count
    return values
