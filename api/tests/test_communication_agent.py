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
from app.services.agents.communication import MODEL_UNAVAILABLE_MESSAGE, CommunicationAgent


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
    assert ctx.draft_answer == (
        "Deve cobrir de 3 a 6 meses de despesas básicas. [1]\n"
        "Despesa média mensal (avg_expense): 2000.0 reais [Fonte auditável: Extrato de Outubro]\n"
        "Falta o dado: Considerando apenas lançamentos de débito confirmados?"
    )
    assert ctx.model == "mock-model"
    assert "model" in step.detail
    assert step.detail["attempt"] == 1
    assert step.detail["draft_guard"] == "safe_fallback"


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
            ),
            ValidationIssue(
                code="STYLE_WARNING",
                severity=IssueSeverity.WARNING,
                message="Prefira uma resposta mais curta.",
            ),
        ],
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.OK
    assert ctx.attempt == 2
    assert len(captured_prompts) == 1
    assert "REVISÃO OBRIGATÓRIA" in captured_prompts[0]
    assert "NUMBER_NOT_SUPPORTED" in captured_prompts[0]
    assert "STYLE_WARNING" not in captured_prompts[0]


@pytest.mark.asyncio
async def test_resposta_literal_com_citacao_e_aceita_sem_premissas():
    class LiteralLLM(MockLLMProvider):
        async def generate(self, prompt: str, **kwargs) -> LLMResponse:
            return LLMResponse(
                content="Deve cobrir de 3 a 6 meses de despesas básicas. [1]",
                model="mock-literal",
            )

    agent = CommunicationAgent(llm_provider=LiteralLLM())
    ctx = AgentContext(
        question="Qual é a orientação?",
        evidences=[
            EvidenceChunk(
                id="ev-1",
                document_title="Caderno BCB",
                section="Reserva",
                content="Deve cobrir de 3 a 6 meses de despesas básicas.",
                source_name="Banco Central do Brasil",
                source_url="https://www.bcb.gov.br",
                score=0.9,
            )
        ],
    )

    step = await agent.run(ctx)

    assert step.detail["draft_guard"] == "accepted"
    assert ctx.draft_answer == "Deve cobrir de 3 a 6 meses de despesas básicas. [1]"
    assert not ctx.issues


@pytest.mark.asyncio
async def test_communication_agent_llm_failure():
    failing_llm = AsyncMock()
    failing_llm.generate.side_effect = ConnectionError("Serviço de IA offline")

    agent = CommunicationAgent(llm_provider=failing_llm)
    ctx = AgentContext(question="Qual o meu saldo?")

    step = await agent.run(ctx)

    assert step.agent == AgentName.COMMUNICATION
    assert step.status == StepStatus.FAILED
    assert step.summary == MODEL_UNAVAILABLE_MESSAGE
    assert step.detail["error_type"] == "ConnectionError"
    assert ctx.draft_answer is None
    assert ctx.attempt == 1


@pytest.mark.asyncio
async def test_conteudo_nao_literal_vira_fallback_com_premissas_exatas():
    prompts = []

    class CapturingLLM(MockLLMProvider):
        async def generate(self, prompt: str, **kwargs) -> LLMResponse:
            prompts.append(prompt)
            return LLMResponse(content="Organize seus gastos com disciplina.", model="mock")

    ctx = AgentContext(
        question="Como organizar o orçamento?",
        evidences=[
            EvidenceChunk(
                id="ev-1",
                document_title="Caderno BCB",
                section="Orçamento",
                content="O orçamento registra receitas e despesas.",
                source_name="Banco Central do Brasil",
                source_url="https://www.bcb.gov.br",
                score=0.9,
            )
        ],
        calculations=[
            CalculationResult(
                key="balance",
                label="Saldo",
                value="12,30",
                unit="BRL",
                source="CalculationService",
            )
        ],
        assumptions=["Falta informar o período do orçamento."],
    )

    step = await CommunicationAgent(CapturingLLM()).run(ctx)

    assert "O orçamento registra receitas e despesas. [1]" in ctx.draft_answer
    assert "Saldo (balance): 12,30 BRL [Fonte auditável: CalculationService]" in ctx.draft_answer
    assert "Falta o dado: Falta informar o período do orçamento?" in ctx.draft_answer
    assert "Organize seus gastos" not in ctx.draft_answer
    assert "Banco Central do Brasil" in prompts[0]
    assert "12,30 BRL" in prompts[0]
    assert "Falta informar o período do orçamento." in prompts[0]
    assert step.detail["draft_guard"] == "safe_fallback"
    assert step.status == StepStatus.OK
    assert ctx.attempt == 1


@pytest.mark.asyncio
async def test_numero_inventado_gera_bloqueio_para_validation():
    class InventingLLM(MockLLMProvider):
        async def generate(self, prompt: str, **kwargs) -> LLMResponse:
            return LLMResponse(
                content="Transfira R$ 888.777,55 para organizar suas contas [1].",
                model="mock-inventado",
            )

    ctx = AgentContext(
        question="Como organizar o orçamento?",
        evidences=[
            EvidenceChunk(
                id="ev-1",
                document_title="Caderno BCB",
                section="Orçamento",
                content="O orçamento registra receitas e despesas.",
                source_name="Banco Central do Brasil",
                source_url="https://www.bcb.gov.br",
                score=0.9,
            )
        ],
    )

    step = await CommunicationAgent(InventingLLM()).run(ctx)

    assert step.status == StepStatus.OK
    assert step.detail["draft_guard"] == "safe_fallback"
    assert "888.777,55" not in ctx.draft_answer
    assert any(issue.code == "DRAFT_NOT_GROUNDED" for issue in ctx.issues)


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
