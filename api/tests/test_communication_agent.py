from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.clients.mock_llm import MockLLMProvider
from app.domain.agents import (
    AgentContext,
    AgentName,
    CalculationResult,
    IssueSeverity,
    StepStatus,
    ValidationIssue,
)
from app.domain.models import EvidenceChunk
from app.models.llm_provider import LLMResponse
from app.services.agents.communication import CommunicationAgent


@pytest.mark.asyncio
async def test_communication_agent_normal_run():
    mock_llm = MockLLMProvider(model_name="mock-model")
    agent = CommunicationAgent(llm_provider=mock_llm)

    ctx = AgentContext(
        question="Qual a regra da reserva de emergência?",
        evidences=[
            EvidenceChunk(
                id="chunk-1",
                document_title="Caderno BCB",
                section="Reserva",
                content="Deve cobrir de 3 a 6 meses de despesas básicas.",
                source_name="Banco Central do Brasil",
                source_url="https://www.bcb.gov.br",
                score=0.9,
            )
        ],
        calculations=[
            CalculationResult(
                label="Despesa média mensal",
                key="avg_expense",
                value=2000.0,
                unit="reais",
                source="Extrato de Outubro",
            )
        ],
        assumptions=["Considerando apenas lançamentos de débito confirmados."],
    )

    step = await agent.run(ctx)

    assert step.agent == AgentName.COMMUNICATION
    assert step.status == StepStatus.OK
    assert ctx.attempt == 1
    assert "Banco Central do Brasil" in ctx.draft_answer
    assert ctx.model == "mock-model"
    assert "model" in step.detail
    assert step.detail["attempt"] == 1


@pytest.mark.asyncio
async def test_communication_agent_revision_prompt():
    captured_prompts: list[str] = []

    class CapturingLLM(MockLLMProvider):
        async def generate(self, prompt: str, **kwargs) -> LLMResponse:
            captured_prompts.append(prompt)
            return LLMResponse(content="Resposta revisada.", model="mock-rev")

    agent = CommunicationAgent(llm_provider=CapturingLLM())
    ctx = AgentContext(
        question="Qual o meu saldo?",
        attempt=1,
        issues=[
            ValidationIssue(
                code="NUMBER_NOT_SUPPORTED",
                severity=IssueSeverity.BLOCKER,
                message="Número R$ 9.999 não tem respaldo nas contas.",
            )
        ],
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.OK
    assert ctx.attempt == 2
    assert len(captured_prompts) == 1
    assert "REVISÃO OBRIGATÓRIA" in captured_prompts[0]
    assert "NUMBER_NOT_SUPPORTED" in captured_prompts[0]


@pytest.mark.asyncio
async def test_communication_agent_llm_failure():
    failing_llm = AsyncMock()
    failing_llm.generate.side_effect = ConnectionError("Serviço de IA offline")

    agent = CommunicationAgent(llm_provider=failing_llm)
    ctx = AgentContext(question="Qual o meu saldo?")

    step = await agent.run(ctx)

    assert step.agent == AgentName.COMMUNICATION
    assert step.status == StepStatus.FAILED
    assert "Falha de comunicação" in step.summary
    assert "Serviço de IA offline" in step.detail["error"]
    assert ctx.draft_answer is None


def test_communication_agent_fallback_template(tmp_path: Path):
    non_existent = tmp_path / "nao_existe.txt"
    agent = CommunicationAgent(
        llm_provider=MockLLMProvider(),
        prompt_path=non_existent,
    )
    assert "{evidences}" in agent.template
    assert "{calculations}" in agent.template


def test_communication_agent_formatters_empty():
    assert "Nenhuma evidência" in CommunicationAgent._format_evidences([])
    assert "Nenhum cálculo" in CommunicationAgent._format_calculations([])
    assert "Nenhuma limitação" in CommunicationAgent._format_assumptions([])
    assert CommunicationAgent._format_revision_notes([], 0) == ""
    assert CommunicationAgent._format_revision_notes([], 1) == ""
