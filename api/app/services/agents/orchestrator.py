import re
import time
import unicodedata
from collections.abc import Sequence
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domain.agents import (
    AgentContext,
    AgentName,
    AgentStep,
    FinancialContext,
    FinancialFilters,
    IssueSeverity,
    MultiAgentResponse,
    MultiAgentStatus,
    StepStatus,
)
from app.domain.models import Transaction
from app.services.agents.base import Agent
from app.services.financial_chat_intent import financial_intent, requires_guidance
from app.services.library_service import Library

ABSTENTION_MESSAGE = (
    "O Trokim não possui evidências suficientes nas diretrizes oficiais "
    "(Banco Central do Brasil, CVM, CFPB ou ANPD) para responder a essa consulta "
    "com segurança. Para sua proteção financeira, recomendamos consultar "
    "canais oficiais regulamentados."
)

REJECTION_MESSAGE = (
    "A resposta preliminar gerada pelo assistente não passou pelas regras de validação "
    "e segurança do Trokim (conformidade com cálculos auditáveis e diretrizes oficiais). "
    "Por segurança financeira, a resposta foi retida."
)

ANALYSIS_KEYWORDS = (
    "saldo",
    "receita",
    "receitas",
    "despesa",
    "despesas",
    "gastei",
    "gasto",
    "gastos",
    "categoria",
    "categorias",
    "poupança",
    "poupanca",
    "poupar",
    "meta",
    "metas",
    "meses",
    "cenário",
    "cenario",
    "cenários",
    "cenarios",
    "projeção",
    "projecao",
    "projeções",
    "projecoes",
    "quanto",
    "orçamento",
    "orcamento",
    "guardar",
    "guardei",
    "economizar",
    "economizei",
)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def needs_analysis(question: str) -> bool:
    """Verifica se a pergunta demanda análise numérica ou cálculos sobre transações."""
    normalized = _strip_accents(question.lower())
    tokens = set(re.findall(r"\b\w+\b", normalized))
    for kw in ANALYSIS_KEYWORDS:
        clean_kw = _strip_accents(kw.lower())
        if clean_kw in tokens or clean_kw in normalized:
            return True
    return False


class Orchestrator:
    """Orquestrador determinístico do fluxo multiagente (Research -> Analysis -> Comm -> Val)."""

    def __init__(
        self,
        research: Agent,
        analysis: Agent,
        communication: Agent,
        validation: Agent,
        max_revisions: int = 1,
    ) -> None:
        self.research = research
        self.analysis = analysis
        self.communication = communication
        self.validation = validation
        self.max_revisions = max_revisions

    @staticmethod
    def _response(
        ctx: AgentContext,
        steps: list[AgentStep],
        status: MultiAgentStatus,
        answer: str,
    ) -> MultiAgentResponse:
        return MultiAgentResponse(
            query=ctx.question,
            status=status,
            answer=answer,
            model=ctx.model,
            evidences=ctx.evidences,
            calculations=ctx.calculations,
            validation_issues=ctx.issues,
            steps=steps,
            total_ms=sum(step.duration_ms for step in steps),
        )

    async def _safe_run(self, agent: Agent, ctx: AgentContext) -> AgentStep:
        t0 = time.perf_counter()
        try:
            step = await agent.run(ctx)
            if step.duration_ms <= 0:
                step.duration_ms = max(1, int(round((time.perf_counter() - t0) * 1000)))
            return step
        except Exception as exc:
            duration = max(1, int(round((time.perf_counter() - t0) * 1000)))
            return AgentStep(
                agent=agent.name,
                status=StepStatus.FAILED,
                summary=f"Falha inesperada no agente {agent.name.value}: {exc}",
                duration_ms=duration,
                detail={"error": str(exc), "error_type": type(exc).__name__},
            )

    async def run(
        self,
        question: str,
        transactions: Sequence[Transaction] = (),
        library: Library | None = None,
        filters: FinancialFilters | None = None,
        reference_date: date | None = None,
    ) -> MultiAgentResponse:
        steps: list[AgentStep] = []
        # O contrato anterior recebe apenas lançamentos (também usado pelo benchmark).
        # Contas, faturas e filtros exigem a biblioteca explícita da RF30.
        intent = financial_intent(question) if library is not None else None
        financial = None
        if library is not None and intent is not None:
            financial = FinancialContext(
                intent=intent,
                reference_date=reference_date or datetime.now(ZoneInfo("America/Sao_Paulo")).date(),
                filters=filters or FinancialFilters(),
                accounts={k: v.model_copy(deep=True) for k, v in library.accounts.items()},
                statements={k: v.model_copy(deep=True) for k, v in library.statements.items()},
            )
        ctx = AgentContext(
            financial=financial,
            question=question.strip(),
            transactions=[
                tx.model_copy(deep=True)
                for tx in (library.transactions if library else transactions)
            ],
        )

        # 1. Research Agent
        if intent and not requires_guidance(question):
            research_step = AgentStep(
                agent=AgentName.RESEARCH,
                status=StepStatus.SKIPPED,
                summary="Consulta aos dados importados; não requer orientação institucional.",
                detail={"reason": "financial_query"},
            )
        else:
            research_step = await self._safe_run(self.research, ctx)
        steps.append(research_step)

        if research_step.status == StepStatus.FAILED:
            return self._response(ctx, steps, MultiAgentStatus.REJECTED, REJECTION_MESSAGE)

        if research_step.status == StepStatus.ABSTAINED or ctx.abstain_reason:
            return MultiAgentResponse(
                query=ctx.question,
                status=MultiAgentStatus.ABSTAINED,
                answer=ABSTENTION_MESSAGE,
                model=ctx.model,
                evidences=[],
                calculations=[],
                validation_issues=[],
                steps=steps,
                total_ms=sum(s.duration_ms for s in steps),
            )

        # 2. Analysis Agent
        if intent or needs_analysis(ctx.question):
            analysis_step = await self._safe_run(self.analysis, ctx)
            steps.append(analysis_step)
            if analysis_step.status == StepStatus.FAILED:
                return self._response(ctx, steps, MultiAgentStatus.REJECTED, REJECTION_MESSAGE)
        else:
            steps.append(
                AgentStep(
                    agent=AgentName.ANALYSIS,
                    status=StepStatus.SKIPPED,
                    summary="Pergunta não requer cálculos numéricos sobre lançamentos.",
                    duration_ms=0,
                    detail={"reason": "needs_analysis_false"},
                )
            )

        if intent and not ctx.calculations:
            ctx.draft_answer = "\n".join(ctx.assumptions)
            steps.append(
                AgentStep(
                    agent=AgentName.COMMUNICATION,
                    status=StepStatus.SKIPPED,
                    summary="Esclarecimento ou dado ausente informado sem chamar o modelo.",
                )
            )
            validation = await self._safe_run(self.validation, ctx)
            steps.append(validation)
            approved = validation.status == StepStatus.OK
            return MultiAgentResponse(
                query=ctx.question,
                status=MultiAgentStatus.ABSTAINED if approved else MultiAgentStatus.REJECTED,
                answer=ctx.draft_answer if approved else REJECTION_MESSAGE,
                steps=steps,
                validation_issues=ctx.issues,
                total_ms=sum(s.duration_ms for s in steps),
            )

        # 3. Communication & Validation Loop
        for revision in range(self.max_revisions + 1):
            comm_step = await self._safe_run(self.communication, ctx)
            steps.append(comm_step)
            if comm_step.status == StepStatus.FAILED:
                return self._response(ctx, steps, MultiAgentStatus.REJECTED, REJECTION_MESSAGE)

            val_step = await self._safe_run(self.validation, ctx)
            steps.append(val_step)
            if val_step.status == StepStatus.FAILED:
                has_blocker = any(i.severity == IssueSeverity.BLOCKER for i in ctx.issues)
                if has_blocker and revision < self.max_revisions:
                    # Permite revisão do Communication Agent
                    continue

                return self._response(ctx, steps, MultiAgentStatus.REJECTED, REJECTION_MESSAGE)

            # Validação aprovada (OK ou avisos informativos)
            return self._response(ctx, steps, MultiAgentStatus.ANSWERED, ctx.draft_answer or "")

        # Se esgotar revisões com rejeição
        return self._response(ctx, steps, MultiAgentStatus.REJECTED, REJECTION_MESSAGE)
