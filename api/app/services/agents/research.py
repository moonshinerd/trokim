"""Recuperação de evidências e abstenção sem modelo de linguagem (RF18 / GQ05)."""

import re
import unicodedata
from time import perf_counter

from app.domain import agents
from app.services.agents.orchestrator import needs_analysis
from app.services.rag_service import RAGService

STRICTLY_FORBIDDEN_PATTERNS = (
    r"\b(escreva|crie|faca|conte|componha|gere)\b.*\b(poema|poesia|musica|conto|roteiro|piada)\b",
    r"\b(ignore|desconsidere|esqueca)\b.*\b(fontes|regras|instrucoes|diretrizes)\b",
    r"\b(garanta|garantir)\b.*\b(lucro|retorno|dinheiro)\b",
    r"\b(qual|quais|diga|indique|escolha|recomende)\b.*\b(acao|acoes|cripto|criptomoeda|criptomoedas)\b",
    r"\b(acao|acoes|cripto|criptomoeda|criptomoedas)\b.*\b(comprar|vender|lucrar|lucro)\b",
    r"\b(aposta|apostas|bet|bets|cassino|jogo do bicho)\b",
    r"\b(descobrir|roubar|obter|revelar)\b.*\b(senha|cpf)\b",
    r"\b(bolo|futebol|copa do mundo|remedio|gripe|horoscopo)\b",
    r"\b(escreva|gere|crie)\b.*\b(codigo|script|programa)\b",
)


def _is_strictly_forbidden(query: str) -> bool:
    normalized = unicodedata.normalize("NFKD", query).encode("ascii", "ignore").decode().lower()
    return any(re.search(pat, normalized) for pat in STRICTLY_FORBIDDEN_PATTERNS)


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
        query = ctx.question.strip()

        # 1. Se for estritamente proibido (apostas, seleção de ativos para compra, código, etc.)
        if _is_strictly_forbidden(query):
            ctx.abstain_reason = "fora_de_escopo"
            summary = "Consulta classificada como fora de escopo institucional."
        elif self.rag_service.is_outside_scope(query):
            # Se for fora de escopo do RAG educacional, mas for consulta de cálculo com
            # lançamentos importados, permite prosseguir para o AnalysisAgent
            if (needs_analysis(query) or len(ctx.transactions) > 0) and len(ctx.transactions) > 0:
                summary = "Nenhuma evidência documental necessária; direcionado para análise."
            else:
                ctx.abstain_reason = "fora_de_escopo"
                summary = "Pergunta fora do escopo de orientação financeira educacional."
        else:
            ctx.evidences = self.rag_service.retrieve_evidence(query)
            if ctx.evidences:
                summary = "Evidências oficiais encontradas para fundamentar a resposta."
            elif needs_analysis(query) and len(ctx.transactions) > 0:
                summary = "Nenhuma evidência documental necessária; direcionado para análise."
            else:
                ctx.abstain_reason = "sem_evidencia"
                summary = "Nenhuma evidência oficial atingiu o limiar de relevância."

        duration_ms = max(0, int((perf_counter() - started) * 1000))
        top_k = getattr(self.rag_service, "top_k", 3)
        threshold = getattr(self.rag_service, "threshold", 0.15)

        return agents.AgentStep(
            agent=self.name,
            status=agents.StepStatus.ABSTAINED if ctx.abstain_reason else agents.StepStatus.OK,
            summary=summary,
            duration_ms=duration_ms,
            detail={
                "top_k": top_k,
                "threshold": threshold,
                "scores": [evidence.score for evidence in ctx.evidences],
                "documents": [evidence.document_title for evidence in ctx.evidences],
            },
        )
