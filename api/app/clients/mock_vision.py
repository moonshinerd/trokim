"""Adaptadores determinísticos de OCR e visão para testes e CI (sem modelo nem OCR instalado)."""

import json

from app.models.vision_provider import OcrResult, OcrWord, VisionResult


class MockOcrProvider:
    name: str = "mock"

    def __init__(self, words: list[tuple[str, float]] | None = None) -> None:
        self.words = words if words is not None else [("COMPROVANTE DE PIX", 0.99)]

    async def read(self, image: bytes) -> OcrResult:
        return OcrResult(
            words=[OcrWord(text=text, confidence=conf) for text, conf in self.words],
            engine=self.name,
        )


class MockVisionProvider:
    name: str = "mock"
    is_remote: bool = False

    def __init__(self, model: str = "mock-vision", fields: dict[str, object] | None = None) -> None:
        self.model = model
        self.fields = fields if fields is not None else {"amount": "10,00"}

    async def extract(
        self,
        image: bytes,
        instructions: str,
        schema: dict[str, object] | None = None,
    ) -> VisionResult:
        return VisionResult(content=json.dumps(self.fields), model=self.model)
