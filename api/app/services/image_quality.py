"""Métricas locais verificadas no corpus sintético da #90; não certificam fotos reais.

O ensaio mantém 320 px, Laplaciano 15 e contraste 12: na calibração não há falso
aceite/rejeição; a validação usa famílias separadas. Confiança 0,80 é política
conservadora de leitura (compartilhada com #89), não probabilidade calibrada.
Textura, moldura e corte não são detectados semanticamente por estas métricas.
"""

import numpy as np
from PIL import Image

from app.domain.documents import DocumentQuality, QualityReport

MIN_SIDE = 320
MIN_SHARPNESS = 15.0
MIN_CONTRAST = 12.0
MIN_OCR_CONFIDENCE = 0.80
MAX_PIXELS = 20_000_000


def assess_quality(image: Image.Image, confidence: float | None = None) -> QualityReport:
    gray = np.asarray(image.convert("L"), dtype=np.float64)
    if min(gray.shape) < 3:
        sharpness = 0.0
    else:
        lap = (
            gray[:-2, 1:-1]
            + gray[2:, 1:-1]
            + gray[1:-1, :-2]
            + gray[1:-1, 2:]
            - 4 * gray[1:-1, 1:-1]
        )
        sharpness = float(lap.var())
    reasons = []
    if min(image.size) < MIN_SIDE:
        reasons.append("resolução insuficiente")
    if sharpness < MIN_SHARPNESS:
        reasons.append("imagem com baixa nitidez")
    if gray.std() < MIN_CONTRAST:
        reasons.append("imagem com pouco contraste")
    quality = DocumentQuality.ILLEGIBLE if reasons else DocumentQuality.LEGIBLE
    if quality == DocumentQuality.LEGIBLE and confidence is not None:
        if confidence < MIN_OCR_CONFIDENCE:
            quality = DocumentQuality.PARTIAL
            reasons.append("leitura com baixa confiança")
    return QualityReport(
        quality=quality,
        sharpness=sharpness,
        resolution=image.size,
        mean_ocr_confidence=confidence,
        reasons=reasons,
    )
