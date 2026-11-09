"""Port abstrato para provedores de síntese generativa (LLMs)."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.domain.models import EvidenceChunk


class LLMResponse(BaseModel):
    """Resposta estruturada gerada pelo provedor de linguagem."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict[str, object] = Field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Contrato abstrato (Port) para modelos de linguagem no Trokim."""

    name: str

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        context_chunks: list[EvidenceChunk] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Gera resposta assíncrona baseada no prompt e contexto regulatório opcional."""
        ...
