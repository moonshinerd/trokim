"""Testes do Research com RAG, contratos e orquestrador reais, sem LLM nem rede."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_rag import FakeEmbedder

from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.domain import agents
from app.services.agents.orchestrator import Orchestrator
from app.services.agents.research import ResearchAgent
from app.services.rag_service import RAGService
from tests.agents.fakes import FakeAnalysisAgent, FakeCommunicationAgent, FakeValidationAgent


@pytest.fixture
def rag(tmp_path) -> RAGService:
    return RAGService(
        embedder=FakeEmbedder(),
        store=SQLiteVectorStore(tmp_path / "research.db", dimension=2),
        alpha=0.0,
        top_k=2,
        threshold=0.15,
    )


@pytest.fixture
def orchestrator(rag) -> Orchestrator:
    return Orchestrator(
        research=ResearchAgent(rag),
        analysis=FakeAnalysisAgent(),
        communication=FakeCommunicationAgent(),
        validation=FakeValidationAgent(),
    )


async def test_pesquisa_preenche_evidencias_e_trilha(rag):
    ctx = agents.AgentContext(question="Como montar uma reserva de emergência?")

    step = await ResearchAgent(rag).run(ctx)

    assert step.agent == agents.AgentName.RESEARCH
    assert step.status == agents.StepStatus.OK
    assert ctx.abstain_reason is None
    assert 0 < len(ctx.evidences) <= rag.top_k
    assert all(evidence.score >= rag.threshold for evidence in ctx.evidences)
    assert all(evidence.source_url.startswith("https://") for evidence in ctx.evidences)
    assert step.detail == {
        "top_k": 2,
        "threshold": 0.15,
        "scores": [evidence.score for evidence in ctx.evidences],
        "documents": [evidence.document_title for evidence in ctx.evidences],
    }
    assert step.summary
    assert step.duration_ms >= 0


@pytest.mark.parametrize(
    "question",
    [
        "Qual aposta esportiva devo fazer para ficar rico?",
        "Qual ação específica devo comprar hoje?",
        "Qual criptomoeda devo comprar?",
        "Invente uma resolução do BCB que garante rendimento sem risco.",
        "Quanto gastei com alimentação?",
    ],
)
async def test_abstencao_por_escopo_nao_executa_busca(rag, monkeypatch, question):
    retrieve = Mock(wraps=rag.retrieve_evidence)
    monkeypatch.setattr(rag, "retrieve_evidence", retrieve)
    ctx = agents.AgentContext(question=question)

    step = await ResearchAgent(rag).run(ctx)

    assert step.status == agents.StepStatus.ABSTAINED
    assert ctx.abstain_reason == "fora_de_escopo"
    assert ctx.evidences == []
    assert step.detail["scores"] == step.detail["documents"] == []
    retrieve.assert_not_called()


async def test_c28_do_gabarito_e_recusado(rag):
    cases_path = (
        Path(__file__).resolve().parents[2] / "research/rag_benchmark/questions_comparison.json"
    )
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    case = next(case for case in cases if case["id"] == "C28")
    ctx = agents.AgentContext(question=case["query"])

    step = await ResearchAgent(rag).run(ctx)

    assert step.status == agents.StepStatus.ABSTAINED
    assert ctx.abstain_reason == "fora_de_escopo"
    assert ctx.evidences == []


async def test_abstencao_sem_evidencia_acima_do_limiar(rag):
    ctx = agents.AgentContext(question="Como montar uma reserva de emergência?")
    assert rag.retrieve_evidence(ctx.question)
    rag.threshold = 1.0

    step = await ResearchAgent(rag).run(ctx)

    assert step.status == agents.StepStatus.ABSTAINED
    assert ctx.abstain_reason == "sem_evidencia"
    assert ctx.evidences == []
    assert step.detail == {"top_k": 2, "threshold": 1.0, "scores": [], "documents": []}


async def test_contexto_reutilizado_nao_preserva_resultados_anteriores(rag):
    agent = ResearchAgent(rag)
    ctx = agents.AgentContext(question="Como montar uma reserva de emergência?")
    assert (await agent.run(ctx)).status == agents.StepStatus.OK

    ctx.question = "Qual criptomoeda devo comprar?"
    assert (await agent.run(ctx)).status == agents.StepStatus.ABSTAINED
    assert ctx.evidences == []
    assert ctx.abstain_reason == "fora_de_escopo"

    ctx.question = "Como montar uma reserva de emergência?"
    rag.threshold = 1.0
    assert (await agent.run(ctx)).status == agents.StepStatus.ABSTAINED
    assert ctx.evidences == []
    assert ctx.abstain_reason == "sem_evidencia"

    rag.threshold = 0.15
    assert (await agent.run(ctx)).status == agents.StepStatus.OK
    assert ctx.evidences
    assert ctx.abstain_reason is None


async def test_erro_de_busca_nao_vira_ausencia_de_evidencia(rag, monkeypatch):
    agent = ResearchAgent(rag)
    ctx = agents.AgentContext(question="Como montar uma reserva de emergência?")
    assert (await agent.run(ctx)).status == agents.StepStatus.OK
    assert ctx.evidences

    def fail(_question):
        raise RuntimeError("Índice indisponível.")

    monkeypatch.setattr(rag, "retrieve_evidence", fail)

    with pytest.raises(RuntimeError, match="Índice indisponível"):
        await agent.run(ctx)

    assert ctx.evidences == []
    assert ctx.abstain_reason is None


async def test_orquestrador_real_recebe_evidencias_e_conclui_fluxo(orchestrator):
    response = await orchestrator.run("O que é uma reserva de emergência?")

    assert response.status == agents.MultiAgentStatus.ANSWERED
    assert response.evidences
    assert response.steps[0].status == agents.StepStatus.OK
    assert response.steps[0].detail["documents"] == [
        evidence.document_title for evidence in response.evidences
    ]
    assert response.steps[1].status == agents.StepStatus.SKIPPED
    assert orchestrator.communication.call_count == 1
    assert orchestrator.validation.call_count == 1
    assert response.total_ms == sum(step.duration_ms for step in response.steps)


@pytest.mark.parametrize(
    "question,threshold",
    [
        ("Qual criptomoeda devo comprar?", 0.15),
        ("Como montar uma reserva de emergência?", 1.0),
    ],
)
async def test_orquestrador_real_interrompe_fluxo_na_abstencao(
    orchestrator, rag, question, threshold
):
    rag.threshold = threshold

    response = await orchestrator.run(question)

    assert response.status == agents.MultiAgentStatus.ABSTAINED
    assert response.evidences == []
    assert len(response.steps) == 1
    assert response.steps[0].status == agents.StepStatus.ABSTAINED
    assert orchestrator.analysis.call_count == 0
    assert orchestrator.communication.call_count == 0
    assert orchestrator.validation.call_count == 0


async def test_orquestrador_real_rejeita_falha_da_busca(orchestrator, rag, monkeypatch):
    monkeypatch.setattr(
        rag, "retrieve_evidence", Mock(side_effect=RuntimeError("Índice indisponível"))
    )

    response = await orchestrator.run("Como montar uma reserva de emergência?")

    assert response.status == agents.MultiAgentStatus.REJECTED
    assert response.evidences == []
    assert len(response.steps) == 1
    assert response.steps[0].status == agents.StepStatus.FAILED
    assert orchestrator.analysis.call_count == 0
    assert orchestrator.communication.call_count == 0
    assert orchestrator.validation.call_count == 0
