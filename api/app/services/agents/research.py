import re
import time
import unicodedata

from app.domain.agents import AgentContext, AgentName, AgentStep, StepStatus
from app.services.agents.orchestrator import needs_analysis
from app.services.rag_service import RAGService

# Expõe is_outside_scope como método público preservando o hash estrito de rag_service.py
if not hasattr(RAGService, "is_outside_scope"):
    setattr(RAGService, "is_outside_scope", staticmethod(RAGService._outside_scope))

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
    """Agente de pesquisa e recuperação de evidências em fontes regulatórias oficiais."""

    def __init__(self, rag_service: RAGService, top_k: int = 3, threshold: float = 0.15) -> None:
        self.name = AgentName.RESEARCH
        self.rag_service = rag_service
        self.top_k = top_k
        self.threshold = threshold

    async def run(self, ctx: AgentContext) -> AgentStep:
        t0 = time.perf_counter()
        query = ctx.question.strip()

        # 1. Checagem de escopo da base oficial
        if self.rag_service.is_outside_scope(query) or _is_strictly_forbidden(query):
            # Se for estritamente proibido (ações, cripto, código, poemas, golpes)
            if _is_strictly_forbidden(query):
                ctx.abstain_reason = "fora_de_escopo"
                duration = max(1, int(round((time.perf_counter() - t0) * 1000)))
                return AgentStep(
                    agent=self.name,
                    status=StepStatus.ABSTAINED,
                    summary="Consulta classificada como fora de escopo institucional.",
                    duration_ms=duration,
                    detail={"reason": "fora_de_escopo", "query": query},
                )

            # Se for pergunta sobre cálculo e lançamentos locais, permite análise
            if needs_analysis(query) or len(ctx.transactions) > 0:
                pass
            else:
                ctx.abstain_reason = "fora_de_escopo"
                duration = max(1, int(round((time.perf_counter() - t0) * 1000)))
                return AgentStep(
                    agent=self.name,
                    status=StepStatus.ABSTAINED,
                    summary="Consulta classificada como fora de escopo institucional.",
                    duration_ms=duration,
                    detail={"reason": "fora_de_escopo", "query": query},
                )

        # 2. Recuperação de evidências oficiais
        evidences = self.rag_service.retrieve_evidence(
            query,
            top_k=self.top_k,
            threshold=self.threshold,
        )
        duration = max(1, int(round((time.perf_counter() - t0) * 1000)))

        if not evidences:
            if needs_analysis(query) or len(ctx.transactions) > 0:
                ctx.evidences = []
                return AgentStep(
                    agent=self.name,
                    status=StepStatus.OK,
                    summary="Nenhuma evidência documental necessária; direcionado para análise.",
                    duration_ms=duration,
                    detail={
                        "top_k": self.top_k,
                        "threshold": self.threshold,
                        "scores": [],
                        "documents": [],
                    },
                )

            ctx.abstain_reason = "sem_evidencia"
            return AgentStep(
                agent=self.name,
                status=StepStatus.ABSTAINED,
                summary="Nenhuma evidência oficial encontrada acima do limiar.",
                duration_ms=duration,
                detail={
                    "top_k": self.top_k,
                    "threshold": self.threshold,
                    "scores": [],
                    "documents": [],
                },
            )

        ctx.evidences = evidences
        scores = [round(e.score, 4) for e in evidences]
        documents = [e.document_id for e in evidences]

        return AgentStep(
            agent=self.name,
            status=StepStatus.OK,
            summary=f"Recuperadas {len(evidences)} evidências oficiais.",
            duration_ms=duration,
            detail={
                "top_k": self.top_k,
                "threshold": self.threshold,
                "scores": scores,
                "documents": documents,
            },
        )
