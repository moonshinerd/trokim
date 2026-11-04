from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rag_service import RAGService

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])

_rag_service = RAGService()


class ChatQueryRequest(BaseModel):
    message: str


class ChatQueryResponse(BaseModel):
    query: str
    answered: bool
    status: str
    answer: str
    evidences: list[dict] = []


@router.post("/ask", response_model=ChatQueryResponse)
async def ask_financial_assistant(request: ChatQueryRequest):
    result = _rag_service.answer_query(request.message)
    return ChatQueryResponse(
        query=result["query"],
        answered=result["answered"],
        status=result["status"],
        answer=result["answer"],
        evidences=result["evidences"],
    )
