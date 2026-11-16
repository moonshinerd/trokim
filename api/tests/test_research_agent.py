import pytest

from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.core.config import settings
from app.domain.agents import AgentContext, AgentName, StepStatus
from app.domain.models import Transaction, TransactionCategory, TransactionType
from app.services.agents.research import ResearchAgent
from app.services.rag_service import RAGService


class FakeEmbedder:
    name: str = "teste-deterministico"
    dimension: int = 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 1.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        if "resolucao 9999" in text.lower() or "inexistente" in text.lower():
            return [1.0, 0.0]  # Ortogonal às evidências -> score baixo
        return [0.0, 1.0]


@pytest.fixture
def rag_service(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RAG_HYBRID_ALPHA", 0.0)
    return RAGService(
        embedder=FakeEmbedder(),
        store=SQLiteVectorStore(tmp_path / "rag.db", dimension=2),
    )


@pytest.mark.asyncio
async def test_research_agent_educational_query_with_evidence(rag_service):
    agent = ResearchAgent(rag_service)
    ctx = AgentContext(question="Como montar uma reserva de emergência?")

    step = await agent.run(ctx)

    assert step.agent == AgentName.RESEARCH
    assert step.status == StepStatus.OK
    assert ctx.abstain_reason is None
    assert len(ctx.evidences) > 0
    assert step.detail["top_k"] == 3
    assert step.detail["threshold"] == 0.15
    assert len(step.detail["documents"]) == len(ctx.evidences)
    assert len(step.detail["scores"]) == len(ctx.evidences)


@pytest.mark.asyncio
async def test_research_agent_outside_scope_queries(rag_service):
    agent = ResearchAgent(rag_service)

    outside_queries = [
        "Recomende uma criptomoeda com lucro garantido",
        "Qual ação devo comprar para lucrar rápido?",
        "Escreva um código em python para calcular juros",
        "Qual o horóscopo de touro para hoje?",
        "Como roubar a senha do banco de alguém?",
    ]

    for q in outside_queries:
        ctx = AgentContext(question=q)
        step = await agent.run(ctx)

        assert step.status == StepStatus.ABSTAINED, f"Falha para query: {q}"
        assert ctx.abstain_reason == "fora_de_escopo"
        assert len(ctx.evidences) == 0


@pytest.mark.asyncio
async def test_research_agent_c28_invented_resolution_abstains(rag_service):
    agent = ResearchAgent(rag_service)
    ctx = AgentContext(
        question="Explique a Resolução 9999 inexistente do BCB sobre empréstimos obrigatórios."
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.ABSTAINED
    assert ctx.abstain_reason == "sem_evidencia"
    assert len(ctx.evidences) == 0
    assert step.detail["scores"] == []


@pytest.mark.asyncio
async def test_research_agent_calculation_query_passes_without_evidence_requirement(rag_service):
    agent = ResearchAgent(rag_service, threshold=0.99)  # Limiar alto para não achar evidência
    ctx = AgentContext(
        question="Qual o meu saldo e quanto gastei no total?",
        transactions=[
            Transaction(
                account_id="acc1",
                description="Salário",
                amount=3000.0,
                date="2026-11-01",
                type=TransactionType.CREDIT,
                category=TransactionCategory.INCOME,
            )
        ],
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.OK
    assert ctx.abstain_reason is None
    assert ctx.evidences == []
    assert "direcionado para análise" in step.summary
