"""Recuperação de evidências e abstenção sem modelo de linguagem (RF18 / GQ05)."""

from time import perf_counter

from app.domain import agents
from app.services.rag_service import RAGService


class ResearchAgent:
    """Aplica a política do RAG e fornece evidências ao fluxo multiagente."""

    name = agents.AgentName.RESEARCH

    def __init__(self, rag_service: RAGService) -> None:
        self.rag_service = rag_service

    async def run(self, ctx: agents.AgentContext) -> agents.AgentStep:
        """Atualiza apenas o resultado da pesquisa e devolve sua trilha de execução."""
        started = perf_counter()
        ctx.evidences = []
        ctx.abstain_reason = None

        if self.rag_service.is_outside_scope(ctx.question):
            ctx.abstain_reason = "fora_de_escopo"
            summary = "Pergunta fora do escopo de orientação financeira educacional."
        else:
            ctx.evidences = self.rag_service.retrieve_evidence(ctx.question)
            if ctx.evidences:
                summary = "Evidências oficiais encontradas para fundamentar a resposta."
            else:
                ctx.abstain_reason = "sem_evidencia"
                summary = "Nenhuma evidência oficial atingiu o limiar de relevância."

        return agents.AgentStep(
            agent=self.name,
            status=agents.StepStatus.ABSTAINED if ctx.abstain_reason else agents.StepStatus.OK,
            summary=summary,
            duration_ms=int((perf_counter() - started) * 1000),
            detail={
                "top_k": self.rag_service.top_k,
                "threshold": self.rag_service.threshold,
                "scores": [evidence.score for evidence in ctx.evidences],
                "documents": [evidence.document_title for evidence in ctx.evidences],
            },
        )
