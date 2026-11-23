"""OCR local com RapidOCR (ONNX), na mesma pilha do FastEmbed. Nada sai da máquina."""

import asyncio
import io
from typing import Any

from app.models.vision_provider import OcrResult, OcrWord


class OcrUnavailableError(RuntimeError):
    """O motor de OCR não está instalado ou não carregou."""


class RapidOcrProvider:
    name: str = "rapidocr"

    def __init__(self) -> None:
        self._engine: Any = None

    def _load(self) -> Any:
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:
                raise OcrUnavailableError(
                    "OCR local indisponível: instale o extra com `uv sync --extra ocr`."
                ) from exc
            self._engine = RapidOCR()
        return self._engine

    def _read_sync(self, image: bytes) -> OcrResult:
        import numpy as np
        from PIL import Image

        pixels = np.array(Image.open(io.BytesIO(image)).convert("RGB"))
        found, _ = self._load()(pixels)
        words: list[OcrWord] = []
        for box, text, confidence in found or []:
            xs = [int(point[0]) for point in box]
            ys = [int(point[1]) for point in box]
            words.append(
                OcrWord(
                    text=str(text),
                    confidence=max(0.0, min(1.0, float(confidence))),
                    box=(min(xs), min(ys), max(xs), max(ys)),
                )
            )
        return OcrResult(words=words, engine=self.name)

    async def read(self, image: bytes) -> OcrResult:
        # O OCR bloqueia a CPU: roda fora do laço de eventos.
        return await asyncio.to_thread(self._read_sync, image)
