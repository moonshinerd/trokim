from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.services.rag_service import RAGService

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@lru_cache
def get_rag_service() -> RAGService:
    return RAGService()


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


@router.post("/ask", response_model=ChatQueryResponse)
async def ask_financial_assistant(
    request: ChatQueryRequest,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> ChatQueryResponse:
    result = rag_service.answer_query(request.message)
    return ChatQueryResponse.model_validate(result)
