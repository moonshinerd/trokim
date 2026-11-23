from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.clients.llm_factory import get_llm_provider
from app.core.request_lifecycle import run_while_connected
from app.domain.agents import MultiAgentResponse
from app.routers.v1.transactions import get_imported_transactions
from app.services.agents.analysis import AnalysisAgent
from app.services.agents.communication import CommunicationAgent
from app.services.agents.orchestrator import Orchestrator
from app.services.agents.research import ResearchAgent
from app.services.agents.validation import ValidationAgent
from app.services.rag_service import RAGService

router = APIRouter(prefix="/agents", tags=["Multi-Agent System"])


class AgentAskRequest(BaseModel):
    document_uid: str | None = Field(default=None, pattern=r"^[0-9a-f]{12}$")
    message: str = Field(
        min_length=1,
        max_length=1000,
        description=(
            "Consulta financeira em linguagem natural a ser processada pelo sistema multiagente."
        ),
        examples=["Como montar uma reserva de emergência e quanto tempo leva?"],
    )


def get_orchestrator() -> Orchestrator:
    """Fábrica de injeção de dependência que monta os 4 agentes do sistema multiagente."""
    return Orchestrator(
        research=ResearchAgent(rag_service=RAGService()),
        analysis=AnalysisAgent(),
        communication=CommunicationAgent(llm_provider=get_llm_provider()),
        validation=ValidationAgent(),
    )


@router.post(
    "/ask",
    response_model=MultiAgentResponse,
    summary="Consulta ao sistema multiagente do Trokim",
    description=(
        "Processa a pergunta através do pipeline multiagente determinístico e auditável: "
        "Research Agent (recuperação e escopo) -> Analysis Agent (cálculos) -> "
        "Communication Agent (redação) -> Validation Agent (auditoria factual defensiva)."
    ),
)
async def ask_multiagent_system(
    request: AgentAskRequest,
    connection: Request,
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> MultiAgentResponse:
    transactions = get_imported_transactions()

    try:
        response = await run_while_connected(
            connection,
            orchestrator.run(
                request.message, transactions=transactions, document_uid=request.document_uid
            ),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="O modelo de linguagem está indisponível no momento. Tente novamente.",
        ) from exc

    # Se a etapa de comunicação falhou por indisponibilidade do modelo
    for step in response.steps:
        if step.agent == "communication" and step.status == "failed":
            raise HTTPException(
                status_code=503,
                detail="O modelo de linguagem está indisponível no momento. Tente novamente.",
            )

    return response
