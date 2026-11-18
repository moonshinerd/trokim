import re
from datetime import date

import pytest
from fastapi.testclient import TestClient
from test_rag import FakeEmbedder

from app.clients.mock_llm import MockLLMProvider
from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.core.config import settings
from app.domain.agents import AgentName, MultiAgentStatus, StepStatus
from app.domain.models import Transaction, TransactionCategory, TransactionType
from app.main import app
from app.models.llm_provider import LLMResponse
from app.routers.v1.agents import get_orchestrator
from app.routers.v1.chat import get_generation_service, get_rag_service
from app.routers.v1.transactions import _LOCAL_TRANSACTIONS
from app.services.agents.analysis import AnalysisAgent
from app.services.agents.communication import CommunicationAgent
from app.services.agents.orchestrator import Orchestrator
from app.services.agents.research import ResearchAgent
from app.services.agents.validation import ValidationAgent
from app.services.generation_service import GenerationService
from app.services.rag_service import RAGService


class GroundedMockLLM(MockLLMProvider):
    async def generate(self, prompt: str, context_chunks=None, **kwargs) -> LLMResponse:
        parts = []
        if context_chunks:
            primary = context_chunks[0]
            parts.append(re.sub(r"([.!?])(?=\s|$)", r"\1 [1]", primary.content.strip()))
        if "CÁLCULOS DO SISTEMA (DETERMINÍSTICOS):" in prompt:
            calculation_section = prompt.split("CÁLCULOS DO SISTEMA (DETERMINÍSTICOS):", 1)[
                1
            ].split("\n\nPREMISSAS", 1)[0]
            parts.extend(
                line[2:].strip()
                for line in calculation_section.splitlines()
                if line.startswith("- ")
            )

        content = "\n".join(parts)
        return LLMResponse(
            content=content,
            model="grounded-mock",
            prompt_tokens=15,
            completion_tokens=25,
        )


class InventingNumberMockLLM(MockLLMProvider):
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        return LLMResponse(
            content=(
                "Com base em fontes oficiais [1], você deve transferir "
                "R$ 888.777,55 para a conta indicada."
            ),
            model="inventing-mock",
            prompt_tokens=10,
            completion_tokens=15,
        )


class FailingMockLLM(MockLLMProvider):
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        raise RuntimeError("Ollama indisponível ou conexão recusada.")


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RAG_HYBRID_ALPHA", 0.0)
    db_path = tmp_path / "agents_test.db"
    rag_service = RAGService(
        embedder=FakeEmbedder(),
        store=SQLiteVectorStore(db_path, dimension=2),
    )
    mock_llm = GroundedMockLLM(model_name="mock-test")

    def override_orchestrator():
        return Orchestrator(
            research=ResearchAgent(rag_service=rag_service),
            analysis=AnalysisAgent(),
            communication=CommunicationAgent(llm_provider=mock_llm),
            validation=ValidationAgent(),
        )

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_orchestrator] = override_orchestrator
    app.dependency_overrides[get_rag_service] = lambda: rag_service
    app.dependency_overrides[get_generation_service] = lambda: GenerationService(
        rag_service=rag_service,
        llm_provider=mock_llm,
    )

    client = TestClient(app)
    _LOCAL_TRANSACTIONS.clear()

    try:
        yield client, rag_service, mock_llm
    finally:
        _LOCAL_TRANSACTIONS.clear()
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_pergunta_so_de_evidencia(test_setup):
    client, _, _ = test_setup
    resp = client.post(
        "/v1/agents/ask",
        json={"message": "Como montar uma reserva de emergência?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in (MultiAgentStatus.ANSWERED, MultiAgentStatus.ABSTAINED)
    assert len(data["steps"]) >= 3
    # Analysis agent foi pulado porque a pergunta não envolve cálculos de transações
    step_agents = [s["agent"] for s in data["steps"]]
    assert AgentName.RESEARCH in step_agents
    assert AgentName.ANALYSIS in step_agents
    assert AgentName.COMMUNICATION in step_agents
    assert AgentName.VALIDATION in step_agents


def test_pergunta_de_saldo_pessoal_abstem_mesmo_com_transacoes(test_setup):
    client, _, _ = test_setup
    # Popula transações na sessão local
    _LOCAL_TRANSACTIONS.extend(
        [
            Transaction(
                id="t1",
                account_id="conta-1",
                date=date(2026, 1, 10),
                description="Salário",
                amount=5000.0,
                type=TransactionType.CREDIT,
                category=TransactionCategory.INCOME,
            ),
            Transaction(
                id="t2",
                account_id="conta-1",
                date=date(2026, 1, 15),
                description="Aluguel",
                amount=1500.0,
                type=TransactionType.DEBIT,
                category=TransactionCategory.HOUSING,
            ),
        ]
    )

    resp = client.post(
        "/v1/agents/ask",
        json={"message": "Qual é o meu saldo atual e gastos?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # A integração de perguntas pessoais com cálculos segue pendente (#58).
    # A presença de transações não deve contornar a política de escopo do Research.
    assert data["status"] == MultiAgentStatus.ABSTAINED
    assert data["calculations"] == []
    assert data["evidences"] == []
    assert data["model"] is None
    assert len(data["steps"]) == 1
    assert data["steps"][0]["agent"] == AgentName.RESEARCH
    assert data["steps"][0]["status"] == StepStatus.ABSTAINED


def test_pergunta_combinada_evidencia_e_calculo(test_setup):
    client, _, _ = test_setup
    _LOCAL_TRANSACTIONS.append(
        Transaction(
            id="t1",
            account_id="conta-1",
            date=date(2026, 1, 10),
            description="Salário",
            amount=4000.0,
            type=TransactionType.CREDIT,
            category=TransactionCategory.INCOME,
        )
    )

    resp = client.post(
        "/v1/agents/ask",
        json={"message": "Com meu saldo de receitas, como organizar o orçamento segundo o BCB?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == MultiAgentStatus.ANSWERED
    assert len(data["steps"]) == 4


def test_abstencao_fora_de_escopo_c28(test_setup):
    client, _, _ = test_setup
    resp = client.post(
        "/v1/agents/ask",
        json={"message": "Qual é a melhor aposta esportiva de bet para ganhar dinheiro?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == MultiAgentStatus.ABSTAINED
    assert "não possui evidências suficientes" in data["answer"].lower()
    # Interrompe no Research Agent
    assert len(data["steps"]) == 1
    assert data["steps"][0]["agent"] == AgentName.RESEARCH
    assert data["steps"][0]["status"] == StepStatus.ABSTAINED


def test_rejeicao_segura_quando_mock_inventa_numero(test_setup, tmp_path):
    client, rag_service, _ = test_setup

    def inventing_orchestrator():
        return Orchestrator(
            research=ResearchAgent(rag_service=rag_service),
            analysis=AnalysisAgent(),
            communication=CommunicationAgent(llm_provider=InventingNumberMockLLM()),
            validation=ValidationAgent(),
            max_revisions=0,
        )

    app.dependency_overrides[get_orchestrator] = inventing_orchestrator

    resp = client.post(
        "/v1/agents/ask",
        json={"message": "Como planejar minha reserva de emergência?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == MultiAgentStatus.REJECTED
    assert "segurança" in data["answer"].lower()


def test_erro_503_quando_modelo_indisponivel(test_setup):
    client, rag_service, _ = test_setup

    def failing_orchestrator():
        return Orchestrator(
            research=ResearchAgent(rag_service=rag_service),
            analysis=AnalysisAgent(),
            communication=CommunicationAgent(llm_provider=FailingMockLLM()),
            validation=ValidationAgent(),
        )

    app.dependency_overrides[get_orchestrator] = failing_orchestrator

    resp = client.post(
        "/v1/agents/ask",
        json={"message": "Como montar uma reserva de emergência?"},
    )
    assert resp.status_code == 503
    assert "indisponível" in resp.json()["detail"].lower()


def test_erro_503_quando_run_while_connected_lanca_runtime_error(test_setup):
    client, _, _ = test_setup
    from unittest.mock import patch

    async def _failing_run(request, coroutine):
        coroutine.close()
        raise RuntimeError("Disconexão forçada")

    with patch("app.routers.v1.agents.run_while_connected", side_effect=_failing_run):
        resp = client.post(
            "/v1/agents/ask",
            json={"message": "Como montar uma reserva de emergência?"},
        )
        assert resp.status_code == 503
        assert "indisponível" in resp.json()["detail"].lower()


def test_validacao_de_entrada(test_setup):
    client, _, _ = test_setup

    # Mensagem vazia
    resp_empty = client.post("/v1/agents/ask", json={"message": ""})
    assert resp_empty.status_code == 422

    # Mensagem longa demais (> 1000 chars)
    resp_long = client.post("/v1/agents/ask", json={"message": "a" * 1001})
    assert resp_long.status_code == 422

    # Tipo inválido (int ao invés de string)
    resp_invalid_type = client.post("/v1/agents/ask", json={"message": 12345})
    assert resp_invalid_type.status_code == 422

    # Mensagem exatamente no limite de 1000 caracteres
    resp_limit = client.post(
        "/v1/agents/ask", json={"message": "Como planejar reserva? " + ("x" * 977)}
    )
    assert resp_limit.status_code == 200


def test_fabrica_get_orchestrator_padrao():
    orch = get_orchestrator()
    assert isinstance(orch, Orchestrator)
    assert orch.research.name == AgentName.RESEARCH
    assert orch.analysis.name == AgentName.ANALYSIS
    assert orch.communication.name == AgentName.COMMUNICATION
    assert orch.validation.name == AgentName.VALIDATION


def test_sem_regressao_nos_endpoints_anteriores(test_setup):
    client, _, _ = test_setup

    # /v1/chat/ask
    resp_ask = client.post(
        "/v1/chat/ask",
        json={"message": "O que é reserva de emergência?"},
    )
    assert resp_ask.status_code == 200
    assert "query" in resp_ask.json()

    # /v1/chat/generate
    resp_gen = client.post(
        "/v1/chat/generate",
        json={"message": "O que é reserva de emergência?", "mode": "grounded"},
    )
    assert resp_gen.status_code == 200
    assert "query" in resp_gen.json()
