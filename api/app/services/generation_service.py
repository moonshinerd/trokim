"""Serviço de síntese generativa (Orquestrador LLM + RAG).

Implementa a geração em linguagem natural ancorada em evidências oficiais
(Banco Central do Brasil, CVM, CFPB e ANPD) utilizando o modelo local Qwen,
com preservação estrita da política de abstenção ética (ADR 0002 e ADR 0003).
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.clients.llm_factory import get_llm_provider
from app.domain.models import EvidenceChunk
from app.models.llm_provider import LLMProvider
from app.services.rag_service import RAGService

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

ABSTENTION_MESSAGE = (
    "O Trokim não possui evidências suficientes nas diretrizes oficiais "
    "(Banco Central do Brasil, CVM, CFPB ou ANPD) para responder a essa consulta "
    "com segurança. Para sua proteção financeira, recomendamos consultar "
    "canais oficiais regulamentados."
)


NO_CALCULATION_RESULTS = "Nenhum resultado determinístico fornecido."


class GenerationResult(BaseModel):
    """Resultado da síntese generativa de linguagem natural."""

    query: str
    answered: bool
    status: Literal["grounded", "abstained", "pure_baseline", "naive_rag"]
    mode: str
    answer: str
    model: str
    evidences: list[EvidenceChunk] = Field(default_factory=list)


class GenerationService:
    """Orquestrador da síntese generativa via Qwen/Ollama e RAG estruturado."""

    def __init__(
        self,
        rag_service: RAGService | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.rag_service = rag_service or RAGService()
        self.llm_provider = llm_provider or get_llm_provider()
        self._load_prompts()

    def _load_prompts(self) -> None:
        grounded_path = PROMPTS_DIR / "prompt_trokim_grounded_v1.txt"
        pure_path = PROMPTS_DIR / "prompt_llm_pure_v1.txt"
        naive_path = PROMPTS_DIR / "prompt_naive_rag_v1.txt"

        self.prompt_grounded_tpl = (
            grounded_path.read_text(encoding="utf-8")
            if grounded_path.exists()
            else "{context}\n{question}"
        )
        self.prompt_pure_tpl = (
            pure_path.read_text(encoding="utf-8") if pure_path.exists() else "{question}"
        )
        self.prompt_naive_tpl = (
            naive_path.read_text(encoding="utf-8")
            if naive_path.exists()
            else "{context}\n{question}"
        )

    @staticmethod
    def _format_context(chunks: list[EvidenceChunk]) -> str:
        formatted_blocks = []
        for idx, chunk in enumerate(chunks, 1):
            source_line = f"[{idx}] Órgão: {chunk.source_name} | Seção: {chunk.section}"
            doc_line = f"Documento: {chunk.document_title}"
            content_line = f"Trecho: {chunk.content.strip()}"
            formatted_blocks.append(f"{source_line}\n{doc_line}\n{content_line}")
        return "\n\n".join(formatted_blocks)

    async def generate_answer(
        self,
        query: str,
        *,
        mode: Literal["grounded", "pure", "naive"] = "grounded",
        top_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """Gera resposta no modo solicitado (grounded com RAG, pure ou naive)."""
        clean_query = query.strip()
        raw_name = getattr(self.llm_provider, "name", "unknown")
        provider_name = raw_name if isinstance(raw_name, str) else "unknown"

        # 1. Modo Grounded (Padrão de Produção do Trokim):
        if mode == "grounded":
            if self.rag_service._outside_scope(clean_query):
                return GenerationResult(
                    query=clean_query,
                    answered=False,
                    status="abstained",
                    mode=mode,
                    answer=ABSTENTION_MESSAGE,
                    model=provider_name,
                    evidences=[],
                )

            evidences = self.rag_service.retrieve_evidence(clean_query, top_k=top_k)
            if not evidences:
                return GenerationResult(
                    query=clean_query,
                    answered=False,
                    status="abstained",
                    mode=mode,
                    answer=ABSTENTION_MESSAGE,
                    model=provider_name,
                    evidences=[],
                )

            context_text = self._format_context(evidences)
            prompt = self.prompt_grounded_tpl.format(
                calculation_results=NO_CALCULATION_RESULTS,
                context=context_text,
                question=clean_query,
            )
            llm_res = await self.llm_provider.generate(
                prompt=prompt,
                context_chunks=evidences,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return GenerationResult(
                query=clean_query,
                answered=True,
                status="grounded",
                mode=mode,
                answer=llm_res.content,
                model=llm_res.model,
                evidences=evidences,
            )

        # 2. Modo Pure (Baseline de LLM pura sem contexto — Semana 3):
        if mode == "pure":
            prompt = self.prompt_pure_tpl.format(
                calculation_results=NO_CALCULATION_RESULTS, question=clean_query
            )
            llm_res = await self.llm_provider.generate(
                prompt=prompt,
                context_chunks=None,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return GenerationResult(
                query=clean_query,
                answered=True,
                status="pure_baseline",
                mode=mode,
                answer=llm_res.content,
                model=llm_res.model,
                evidences=[],
            )

        # 3. Modo Naive (RAG ingênuo sem política de abstenção — Semana 3):
        naive_chunks = self.rag_service.retrieve_evidence(clean_query, top_k=top_k, threshold=0.05)
        context_text = (
            self._format_context(naive_chunks)
            if naive_chunks
            else "Nenhum trecho relevante recuperado."
        )
        prompt = self.prompt_naive_tpl.format(
            calculation_results=NO_CALCULATION_RESULTS,
            context=context_text,
            question=clean_query,
        )
        llm_res = await self.llm_provider.generate(
            prompt=prompt,
            context_chunks=naive_chunks,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return GenerationResult(
            query=clean_query,
            answered=True,
            status="naive_rag",
            mode=mode,
            answer=llm_res.content,
            model=llm_res.model,
            evidences=naive_chunks,
        )
