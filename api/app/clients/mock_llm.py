"""Adaptador Mock para síntese generativa em testes e CI."""

import hashlib

from app.domain.models import EvidenceChunk
from app.models.llm_provider import LLMResponse


class MockLLMProvider:
    """Provedor determinístico para testes e CI local/GitHub Actions sem dependência externa."""

    name: str = "mock"

    def __init__(self, model_name: str = "qwen2.5-mock") -> None:
        self.model_name = model_name

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        context_chunks: list[EvidenceChunk] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Gera resposta simulada e determinística baseada nas evidências fornecidas."""
        if context_chunks:
            primary = context_chunks[0]
            content = (
                f"Com base nas diretrizes oficiais do {primary.source_name} "
                f"({primary.section}):\n\n"
                f"{primary.content}\n\n"
                f"Orientação pedagógica: Para sua segurança financeira e planejamento sustentável, "
                f"consulte as fontes oficiais do {primary.source_name} "
                f"({primary.document_title})."
            )
        else:
            digest = hashlib.sha256(prompt.encode()).hexdigest()[:8]
            short_prompt = prompt.strip()[:80]
            content = (
                f"Síntese informativa geral ({self.model_name} #{digest}): "
                f"Esta é uma resposta generativa direta baseada no conhecimento prévio do modelo, "
                f"sem evidências regulatórias externas indexadas para a pergunta: {short_prompt}."
            )

        return LLMResponse(
            content=content,
            model=self.model_name,
            prompt_tokens=max(1, len(prompt.split())),
            completion_tokens=max(1, len(content.split())),
            raw={"provider": "mock", "simulated": True},
        )
