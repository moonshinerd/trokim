from app.domain.agents import (
    AgentContext,
    AgentName,
    AgentStep,
    CalculationResult,
    EvidenceChunk,
    StepStatus,
    ValidationIssue,
)


class FakeResearchAgent:
    def __init__(
        self,
        status: StepStatus = StepStatus.OK,
        evidences: list[EvidenceChunk] | None = None,
        abstain_reason: str | None = None,
        summary: str = "Recuperação concluída",
        should_raise: Exception | None = None,
    ) -> None:
        self.name = AgentName.RESEARCH
        self.status = status
        self.evidences = (
            evidences
            if evidences is not None
            else [
                EvidenceChunk(
                    id="doc1",
                    document_id="bcb_orcamento.txt",
                    source_name="Banco Central do Brasil",
                    document_title="Orçamento Pessoal",
                    section="Introdução",
                    content=(
                        "Regra 50/30/20 divide orçamento entre necessidades, desejos e poupança."
                    ),
                    score=0.9,
                )
            ]
        )
        self.abstain_reason = abstain_reason
        self.summary = summary
        self.should_raise = should_raise
        self.call_count = 0

    async def run(self, ctx: AgentContext) -> AgentStep:
        self.call_count += 1
        if self.should_raise:
            raise self.should_raise

        if self.abstain_reason:
            ctx.abstain_reason = self.abstain_reason
            return AgentStep(
                agent=self.name,
                status=StepStatus.ABSTAINED,
                summary=self.summary,
                duration_ms=10,
                detail={"reason": self.abstain_reason},
            )

        ctx.evidences = list(self.evidences)
        return AgentStep(
            agent=self.name,
            status=self.status,
            summary=self.summary,
            duration_ms=12,
            detail={"count": len(ctx.evidences)},
        )


class FakeAnalysisAgent:
    def __init__(
        self,
        status: StepStatus = StepStatus.OK,
        calculations: list[CalculationResult] | None = None,
        assumptions: list[str] | None = None,
        summary: str = "Cálculo determinístico finalizado",
        should_raise: Exception | None = None,
    ) -> None:
        self.name = AgentName.ANALYSIS
        self.status = status
        self.calculations = calculations or [
            CalculationResult(
                key="net_balance",
                label="Saldo líquido",
                value=1500.0,
                unit="BRL",
                source="CalculationService.calculate_summary",
            )
        ]
        self.assumptions = assumptions or ["Considerados apenas lançamentos não duplicados."]
        self.summary = summary
        self.should_raise = should_raise
        self.call_count = 0

    async def run(self, ctx: AgentContext) -> AgentStep:
        self.call_count += 1
        if self.should_raise:
            raise self.should_raise

        ctx.calculations.extend(self.calculations)
        ctx.assumptions.extend(self.assumptions)
        return AgentStep(
            agent=self.name,
            status=self.status,
            summary=self.summary,
            duration_ms=8,
            detail={"calculations_count": len(ctx.calculations)},
        )


class FakeCommunicationAgent:
    def __init__(
        self,
        responses: list[str] | None = None,
        model: str = "mock-llm",
        summary: str = "Rascunho elaborado em pt-BR",
        should_raise: Exception | None = None,
    ) -> None:
        self.name = AgentName.COMMUNICATION
        self.responses = responses or ["Resposta gerada com suporte em [1]."]
        self.model = model
        self.summary = summary
        self.should_raise = should_raise
        self.call_count = 0

    async def run(self, ctx: AgentContext) -> AgentStep:
        self.call_count += 1
        if self.should_raise:
            raise self.should_raise

        idx = min(ctx.attempt, len(self.responses) - 1)
        ctx.draft_answer = self.responses[idx]
        ctx.model = self.model
        ctx.attempt += 1

        return AgentStep(
            agent=self.name,
            status=StepStatus.OK,
            summary=self.summary,
            duration_ms=25,
            detail={"attempt": ctx.attempt, "model": self.model},
        )


class FakeValidationAgent:
    def __init__(
        self,
        outcomes: list[tuple[StepStatus, list[ValidationIssue]]] | None = None,
        summary: str = "Validação concluída",
        should_raise: Exception | None = None,
    ) -> None:
        self.name = AgentName.VALIDATION
        self.outcomes = outcomes or [(StepStatus.OK, [])]
        self.summary = summary
        self.should_raise = should_raise
        self.call_count = 0

    async def run(self, ctx: AgentContext) -> AgentStep:
        self.call_count += 1
        if self.should_raise:
            raise self.should_raise

        idx = min(self.call_count - 1, len(self.outcomes) - 1)
        status, issues = self.outcomes[idx]
        ctx.issues = list(issues)

        return AgentStep(
            agent=self.name,
            status=status,
            summary=self.summary,
            duration_ms=15,
            detail={"issues_count": len(issues)},
        )
