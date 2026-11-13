from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.request_lifecycle import run_while_connected
from app.services.generation_service import GenerationService
from app.services.rag_service import RAGService

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@lru_cache
def get_rag_service() -> RAGService:
    return RAGService()


@lru_cache
def get_generation_service() -> GenerationService:
    return GenerationService()


class ChatQueryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class EvidenceResponse(BaseModel):
    id: str
    document_id: str
    source_name: str
    source_url: str | None = None
    document_title: str
    section: str
    content: str
    score: float


class ChatQueryResponse(BaseModel):
    query: str
    answered: bool
    status: Literal["grounded", "abstained"]
    answer: str
    evidences: list[EvidenceResponse] = Field(default_factory=list)


class GenerateQueryRequest(BaseModel):
    """Requisição para síntese generativa via modelo local Qwen e RAG."""

    message: str = Field(
        min_length=1,
        max_length=1000,
        description="Consulta financeira em linguagem natural a ser sintetizada pelo Trokim.",
        examples=["Como montar uma reserva de emergência e onde investir?"],
    )
    mode: Literal["grounded", "pure", "naive"] = Field(
        default="grounded",
        description=(
            "Modo de síntese: 'grounded' (Trokim com evidências oficiais e abstenção ativa), "
            "'pure' (LLM pura baseline) ou 'naive' (RAG ingênuo sem política estrita)."
        ),
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Número de evidências regulatórias a recuperar no contexto.",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperatura de amostragem do modelo Qwen.",
    )


class GenerateQueryResponse(BaseModel):
    """Resposta estruturada gerada em linguagem natural fundamentada."""

    query: str
    answered: bool
    status: Literal["grounded", "abstained", "pure_baseline", "naive_rag"]
    mode: str
    answer: str
    model: str
    evidences: list[EvidenceResponse] = Field(default_factory=list)


@router.post("/ask", response_model=ChatQueryResponse)
async def ask_financial_assistant(
    request: ChatQueryRequest,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> ChatQueryResponse:
    result = rag_service.answer_query(request.message)
    return ChatQueryResponse.model_validate(result)


@router.post(
    "/generate",
    response_model=GenerateQueryResponse,
    summary="Síntese generativa fundamentada com Qwen e RAG estruturado",
    description=(
        "Executa a síntese de respostas em linguagem natural ancorada nas fontes oficiais "
        "regulatórias (Banco Central, CVM, CFPB, ANPD) via modelo local Qwen, "
        "com garantia de abstenção ativa em temas de alto risco ou fora de escopo (ADR 0002/0003)."
    ),
)
async def generate_financial_response(
    request: GenerateQueryRequest,
    connection: Request,
    generation_service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerateQueryResponse:
    result = await run_while_connected(
        connection,
        generation_service.generate_answer(
            request.message,
            mode=request.mode,
            top_k=request.top_k,
            temperature=request.temperature,
        ),
    )
    return GenerateQueryResponse.model_validate(result.model_dump())
