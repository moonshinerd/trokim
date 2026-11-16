import pytest

from app.domain.agents import (
    AgentName,
    IssueSeverity,
    MultiAgentStatus,
    StepStatus,
    ValidationIssue,
)
from app.services.agents.orchestrator import (
    ABSTENTION_MESSAGE,
    REJECTION_MESSAGE,
    Orchestrator,
    needs_analysis,
)
from tests.agents.fakes import (
    FakeAnalysisAgent,
    FakeCommunicationAgent,
    FakeResearchAgent,
    FakeValidationAgent,
)


def test_needs_analysis_detects_numerical_and_budget_queries():
    assert needs_analysis("Qual o meu saldo atual?") is True
    assert needs_analysis("Quanto gastei em alimentação no mês?") is True
    assert needs_analysis("Mostre minhas receitas e despesas") is True
    assert needs_analysis("Qual a minha maior categoria de gastos?") is True
    assert needs_analysis("Quanto preciso poupar para minha meta?") is True
    assert needs_analysis("Em quantos meses consigo juntar R$ 5.000?") is True
    assert needs_analysis("Simule um cenário de corte de despesas") is True
    assert needs_analysis("Qual a projeção para o final do ano?") is True
    assert needs_analysis("Como montar um orçamento pessoal?") is True


def test_needs_analysis_ignores_pure_educational_queries():
    assert needs_analysis("O que é o Fundo Garantidor de Créditos?") is False
    assert needs_analysis("Explique a regra 50/30/20") is False
    assert needs_analysis("O que é liquidez diária?") is False
    assert needs_analysis("Como funciona a diversificação de risco?") is False


@pytest.mark.asyncio
async def test_orchestrator_abstention_stops_without_calling_communication_or_analysis():
    research = FakeResearchAgent(abstain_reason="fora_de_escopo")
    analysis = FakeAnalysisAgent()
    communication = FakeCommunicationAgent()
    validation = FakeValidationAgent()

    orchestrator = Orchestrator(research, analysis, communication, validation)
    res = await orchestrator.run("Qual a cotação do bitcoin hoje?")

    assert res.status == MultiAgentStatus.ABSTAINED
    assert res.answer == ABSTENTION_MESSAGE
    assert len(res.steps) == 1
    assert res.steps[0].agent == AgentName.RESEARCH
    assert res.steps[0].status == StepStatus.ABSTAINED
    assert research.call_count == 1
    assert analysis.call_count == 0
    assert communication.call_count == 0
    assert validation.call_count == 0


@pytest.mark.asyncio
async def test_orchestrator_analysis_skipped_for_non_numeric_question():
    research = FakeResearchAgent()
    analysis = FakeAnalysisAgent()
    communication = FakeCommunicationAgent(responses=["Educação financeira básica conforme [1]."])
    validation = FakeValidationAgent(outcomes=[(StepStatus.OK, [])])

    orchestrator = Orchestrator(research, analysis, communication, validation)
    res = await orchestrator.run("O que é a reserva de emergência segundo a CVM?")

    assert res.status == MultiAgentStatus.ANSWERED
    assert len(res.steps) == 4
    assert res.steps[0].agent == AgentName.RESEARCH and res.steps[0].status == StepStatus.OK
    assert res.steps[1].agent == AgentName.ANALYSIS and res.steps[1].status == StepStatus.SKIPPED
    assert res.steps[2].agent == AgentName.COMMUNICATION and res.steps[2].status == StepStatus.OK
    assert res.steps[3].agent == AgentName.VALIDATION and res.steps[3].status == StepStatus.OK
    assert analysis.call_count == 0
    assert communication.call_count == 1
    assert validation.call_count == 1
    assert res.total_ms > 0


@pytest.mark.asyncio
async def test_orchestrator_runs_analysis_when_needed():
    research = FakeResearchAgent()
    analysis = FakeAnalysisAgent()
    communication = FakeCommunicationAgent(responses=["Seu saldo líquido calculado é R$ 1.500,00."])
    validation = FakeValidationAgent(outcomes=[(StepStatus.OK, [])])

    orchestrator = Orchestrator(research, analysis, communication, validation)
    res = await orchestrator.run("Qual é o meu saldo atual?")

    assert res.status == MultiAgentStatus.ANSWERED
    assert len(res.steps) == 4
    assert res.steps[1].agent == AgentName.ANALYSIS and res.steps[1].status == StepStatus.OK
    assert analysis.call_count == 1
    assert len(res.calculations) >= 1
    assert res.calculations[0].key == "net_balance"


@pytest.mark.asyncio
async def test_orchestrator_revises_on_blocker_and_approves():
    research = FakeResearchAgent()
    analysis = FakeAnalysisAgent()
    communication = FakeCommunicationAgent(
        responses=[
            "Rascunho inicial com número 999 sem suporte.",
            "Rascunho corrigido com saldo de R$ 1.500,00 conforme [1].",
        ]
    )
    # 1ª validação falha com BLOCKER; 2ª validação aprova
    validation = FakeValidationAgent(
        outcomes=[
            (
                StepStatus.FAILED,
                [
                    ValidationIssue(
                        code="NUMBER_NOT_SUPPORTED",
                        severity=IssueSeverity.BLOCKER,
                        message="Número sem suporte: 999",
                    )
                ],
            ),
            (StepStatus.OK, []),
        ]
    )

    orchestrator = Orchestrator(research, analysis, communication, validation, max_revisions=1)
    res = await orchestrator.run("Qual o meu saldo?")

    assert res.status == MultiAgentStatus.ANSWERED
    assert "Rascunho corrigido" in res.answer
    assert communication.call_count == 2
    assert validation.call_count == 2
    # Trilha: Research, Analysis, Comm 1, Val 1, Comm 2, Val 2
    assert len(res.steps) == 6
    assert res.steps[2].agent == AgentName.COMMUNICATION
    assert res.steps[3].agent == AgentName.VALIDATION and res.steps[3].status == StepStatus.FAILED
    assert res.steps[4].agent == AgentName.COMMUNICATION
    assert res.steps[5].agent == AgentName.VALIDATION and res.steps[5].status == StepStatus.OK


@pytest.mark.asyncio
async def test_orchestrator_persistent_blocker_leads_to_rejection():
    research = FakeResearchAgent()
    analysis = FakeAnalysisAgent()
    communication = FakeCommunicationAgent(
        responses=["Rascunho 1 insistente", "Rascunho 2 ainda com erro"]
    )
    blocker_issue = ValidationIssue(
        code="NUMBER_NOT_SUPPORTED",
        severity=IssueSeverity.BLOCKER,
        message="Número sem suporte repetido",
    )
    validation = FakeValidationAgent(
        outcomes=[
            (StepStatus.FAILED, [blocker_issue]),
            (StepStatus.FAILED, [blocker_issue]),
        ]
    )

    orchestrator = Orchestrator(research, analysis, communication, validation, max_revisions=1)
    res = await orchestrator.run("Qual o meu saldo?")

    assert res.status == MultiAgentStatus.REJECTED
    assert res.answer == REJECTION_MESSAGE
    assert len(res.validation_issues) == 1
    assert res.validation_issues[0].code == "NUMBER_NOT_SUPPORTED"
    assert communication.call_count == 2
    assert validation.call_count == 2


@pytest.mark.asyncio
async def test_orchestrator_unexpected_agent_exception_handled_as_failed_step():
    research = FakeResearchAgent(should_raise=RuntimeError("Banco vetorial indisponível"))
    analysis = FakeAnalysisAgent()
    communication = FakeCommunicationAgent()
    validation = FakeValidationAgent()

    orchestrator = Orchestrator(research, analysis, communication, validation)
    res = await orchestrator.run("Como economizar?")

    assert res.status == MultiAgentStatus.REJECTED
    assert res.answer == REJECTION_MESSAGE
    assert len(res.steps) == 1
    assert res.steps[0].agent == AgentName.RESEARCH
    assert res.steps[0].status == StepStatus.FAILED
    assert "Banco vetorial indisponível" in res.steps[0].summary
    assert res.steps[0].detail["error_type"] == "RuntimeError"
