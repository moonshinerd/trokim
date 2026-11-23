"""Portas abstratas de leitura de imagem: OCR e modelo de visão (ADR 0021).

Seguem o padrão do ``LLMProvider`` ([ADR 0009]): quem usa a porta não sabe qual motor há por
trás, e trocar o motor é só configuração. Nenhuma implementação pode registrar em log a imagem,
o texto lido ou o JSON devolvido pelo modelo.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class OcrWord(BaseModel):
    """Um trecho de texto lido, com a confiança do motor (0 a 1) e a caixa em pixels."""

    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    box: tuple[int, int, int, int] | None = None  # x0, y0, x1, y1


class OcrResult(BaseModel):
    words: list[OcrWord] = Field(default_factory=list)
    engine: str

    @property
    def text(self) -> str:
        return "\n".join(word.text for word in self.words)

    @property
    def mean_confidence(self) -> float | None:
        if not self.words:
            return None
        return sum(word.confidence for word in self.words) / len(self.words)


class VisionResult(BaseModel):
    """Resposta crua do modelo de visão: um JSON como texto, validado depois pelo agente."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@runtime_checkable
class OcrProvider(Protocol):
    name: str

    async def read(self, image: bytes) -> OcrResult:
        """Lê o texto de uma imagem (JPEG ou PNG)."""
        ...


@runtime_checkable
class VisionProvider(Protocol):
    name: str
    model: str
    is_remote: bool

    async def extract(
        self,
        image: bytes,
        instructions: str,
        schema: dict[str, object] | None = None,
    ) -> VisionResult:
        """Pede ao modelo de visão os campos da imagem, em JSON, conforme ``schema``."""
        ...
