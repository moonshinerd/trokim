import re
from datetime import date

import pytest
from fastapi.testclient import TestClient
from test_financial_queries import CC, CP
from test_financial_queries import library as financial_library  # noqa: F401
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
    store = SQLiteVectorStore(db_path, dimension=2)
    rag_service = RAGService(embedder=FakeEmbedder(), store=store)
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
        store.engine.dispose()
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


def test_pergunta_de_saldo_pessoal_calcula_sem_exigir_rag(test_setup):
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
    assert data["status"] == MultiAgentStatus.ANSWERED
    values = {calc["key"]: calc["value"] for calc in data["calculations"]}
    assert values == {"total_income": 5000.0, "total_expenses": 1500.0, "net_balance": 3500.0}
    assert data["steps"][0]["status"] == StepStatus.SKIPPED
    assert data["steps"][-1]["status"] == StepStatus.OK


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


@pytest.fixture
def financial_session(test_setup, monkeypatch, request):
    fixture_library = request.getfixturevalue("financial_library")
    from datetime import datetime

    from app.services.library_service import LIBRARY

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 20, 12, tzinfo=tz)

    monkeypatch.setattr("app.services.agents.orchestrator.datetime", FixedDateTime)
    LIBRARY.accounts.update(fixture_library.accounts)
    LIBRARY.statements.update(fixture_library.statements)
    LIBRARY.transactions.extend(fixture_library.transactions)
    client, rag, _ = test_setup

    class CapturingLLM(GroundedMockLLM):
        def __init__(self):
            super().__init__()
            self.prompts = []

        async def generate(self, prompt, **kwargs):
            self.prompts.append(prompt)
            return await super().generate(prompt, **kwargs)

    provider = CapturingLLM()
    orchestrator = Orchestrator(
        ResearchAgent(rag),
        AnalysisAgent(),
        CommunicationAgent(provider),
        ValidationAgent(),
    )
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    return client, LIBRARY, provider, orchestrator


@pytest.mark.parametrize(
    ("message", "filters", "key", "value"),
    [
        ("Quanto falta pagar das minhas parcelas?", {}, "installments_remaining", 200.0),
        ("Quais são minhas dívidas?", {}, "closed_statement_due", 425.5),
        ("Qual o valor da minha fatura fechada pessoal do Nubank?", {}, "statement_fechada", 450.4),
        ("Qual o valor da minha fatura aberta pessoal do Nubank?", {}, "statement_aberta", 190.0),
        ("Quanto gastei na empresa em outubro de 2026?", {}, "total_expenses", 75.1),
        (
            "Quanto gastei?",
            {"account_id": CC, "owner": "pessoal", "period": "2026-11"},
            "total_expenses",
            350.25,
        ),
        ("Quanto gastei em alimentação em novembro de 2026?", {}, "top_category_1", 350.25),
        ("Onde mais gastei em novembro de 2026?", {}, "top_merchant_1", 650.75),
        ("Compare outubro de 2026 e novembro de 2026", {}, "compare_delta", -535.0),
        ("Quanto saiu em transferências em novembro de 2026?", {}, "own_transfers_out", 100.0),
        (
            "Quanto falta pagar das minhas parcelas?",
            {"account_id": CP},
            "installments_remaining",
            200.0,
        ),
    ],
)
def test_consultas_financeiras_ponta_a_ponta(financial_session, message, filters, key, value):
    client, _, _, _ = financial_session
    response = client.post("/v1/agents/ask", json={"message": message, **filters})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered", data
    calc = next(c for c in data["calculations"] if c["key"] == key)
    assert calc["value"] == pytest.approx(value)
    assert calc["source"] == "FinancialQueryService"
    analysis = next(s for s in data["steps"] if s["agent"] == "analysis")
    assert calc in analysis["detail"]["calculations"]
    assert data["steps"][-1]["status"] == "ok"


@pytest.mark.parametrize(
    ("message", "filters", "fragment"),
    [
        ("Qual minha fatura fechada do Nubank?", {}, "Qual delas"),
        ("Quanto gastei em setembro de 2026?", {}, "Não há dados importados"),
        ("Qual minha fatura fechada do Inter?", {}, "Inter"),
        ("Quanto gastei?", {"account_id": "desconhecida"}, "não foi importada"),
        ("Quanto gastei na empresa?", {"owner": "pessoal"}, "diferentes"),
        ("Quanto gastei em outubro de 2026?", {"period": "2026-11"}, "diferentes"),
        ("Qual minha fatura fechada do Nubank?", {"account_id": "bb:conta"}, "não combina"),
        ("Quanto gastei na semana passada?", {}, "período"),
        ("Quanto gastei?", {"period": "2026-99"}, "inválido"),
        ("Quanto gastei?", {"period": "semana passada"}, "filtro de período"),
        ("Compare meus gastos", {}, "dois períodos"),
        ("O que vence nos próximos 60 dias?", {}, "30 dias"),
    ],
)
def test_ambiguidades_e_dados_ausentes_nao_chamam_modelo(
    financial_session, message, filters, fragment
):
    client, _, provider, _ = financial_session
    data = client.post("/v1/agents/ask", json={"message": message, **filters}).json()
    assert data["status"] == "abstained", data
    assert not data["calculations"]
    assert fragment.lower() in data["answer"].lower()
    assert provider.prompts == []


def test_mes_ambiguo_pede_ano(financial_session):
    client, lib, _, _ = financial_session
    lib.transactions.append(lib.transactions[0].model_copy(update={"date": date(2025, 10, 1)}))
    data = client.post("/v1/agents/ask", json={"message": "Quanto gastei em outubro?"}).json()
    assert data["status"] == "abstained"
    assert "qual ano" in data["answer"]
    assert not data["calculations"]


def test_periodo_sem_gasto_com_extrato_importado_pode_ter_zero(financial_session):
    client, lib, _, _ = financial_session
    from app.domain.models import AccountKind, Statement

    lib.statements["vazio"] = Statement(
        id="vazio",
        account_id=CC,
        filename="sintetico.ofx",
        kind=AccountKind.CHECKING,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
    )
    data = client.post(
        "/v1/agents/ask",
        json={
            "message": "Quanto gastei?",
            "account_id": CC,
            "period": "2026-09",
        },
    ).json()
    assert data["status"] == "answered", data
    assert next(c["value"] for c in data["calculations"] if c["key"] == "total_expenses") == 0


def test_prompt_recebe_so_agregados_e_nao_a_pergunta_crua(financial_session):
    client, lib, provider, _ = financial_session
    lib.accounts[CC].acct_id = "987654321-SECRETO"
    lib.accounts[CC].label = "Nome Particular Sigiloso"
    lib.transactions[0].description = "DESCRICAO CRUA SIGILOSA"
    lib.transactions[0].counterparty_doc = "CPF-SIGILOSO"
    data = client.post(
        "/v1/agents/ask",
        json={
            "message": "Qual meu saldo? Meu CPF é CPF-SIGILOSO",
            "account_id": CC,
        },
    ).json()
    assert data["status"] == "answered", data
    assert provider.prompts
    prompt = provider.prompts[0]
    for secret in (
        "987654321-SECRETO",
        "Nome Particular Sigiloso",
        "DESCRICAO CRUA SIGILOSA",
        "CPF-SIGILOSO",
        CC,
    ):
        assert secret not in prompt
    assert "FinancialQueryService" in prompt


def test_numero_da_pergunta_nao_autoriza_resultado_pessoal(financial_session):
    client, _, _, orchestrator = financial_session

    class EchoNumber(MockLLMProvider):
        async def generate(self, **kwargs):
            return LLMResponse(content="Seu saldo é R$ 999,99.", model="mock")

    orchestrator.communication = CommunicationAgent(EchoNumber())
    response = client.post("/v1/agents/ask", json={"message": "Meu saldo é R$ 999,99?"})
    data = response.json()
    assert data["status"] == "rejected", data
    assert "999,99" not in data["answer"]
    assert any(i["code"] == "NUMBER_NOT_SUPPORTED" for i in data["validation_issues"])


def test_filtros_invalidos_rejeitados_pelo_contrato(test_setup):
    client, _, _ = test_setup
    for filters in ({"owner": "outro"}, {"account_id": ""}, {"period": 123}):
        assert (
            client.post("/v1/agents/ask", json={"message": "Saldo?", **filters}).status_code == 422
        )


@pytest.mark.parametrize(
    ("message", "filters", "key", "value"),
    [
        ("Qual minha fatura fechada do Nubank?", {"owner": "empresa"}, "statement_fechada", 75.1),
        ("Quanto gastei em outubro de 2026?", {"period": "2026-10"}, "total_expenses", 1726.0),
        ("Gastei mais em outubro de 2026 ou em novembro de 2026?", {}, "compare_delta", -535.0),
    ],
)
def test_filtros_desambiguam_sem_alterar_o_recorte(financial_session, message, filters, key, value):
    client, _, _, _ = financial_session
    data = client.post("/v1/agents/ask", json={"message": message, **filters}).json()
    assert data["status"] == "answered", data
    assert next(c["value"] for c in data["calculations"] if c["key"] == key) == pytest.approx(value)


def test_ano_do_filtro_desambigua_mes_do_texto(financial_session):
    client, lib, _, _ = financial_session
    lib.transactions.append(lib.transactions[0].model_copy(update={"date": date(2025, 10, 1)}))
    data = client.post(
        "/v1/agents/ask", json={"message": "Quanto gastei em outubro?", "period": "2026-10"}
    ).json()
    assert data["status"] == "answered", data


def test_contas_em_separado_respeitam_dono(financial_session):
    client, _, _, _ = financial_session
    data = client.post(
        "/v1/agents/ask",
        json={"message": "Quanto gastei por conta?", "owner": "empresa", "period": "2026-10"},
    ).json()
    assert data["status"] == "answered", data
    assert all("empresa" in c["label"] for c in data["calculations"])
    assert sorted(c["value"] for c in data["calculations"] if c["key"].endswith("expenses")) == [
        0,
        75.1,
    ]


def test_pedido_de_orientacao_nao_contorna_research(financial_session):
    from unittest.mock import AsyncMock

    from app.domain.agents import AgentStep

    client, _, provider, orchestrator = financial_session
    orchestrator.research.run = AsyncMock(
        return_value=AgentStep(
            agent=AgentName.RESEARCH,
            status=StepStatus.ABSTAINED,
            summary="Sem evidência.",
        )
    )
    data = client.post(
        "/v1/agents/ask", json={"message": "Qual meu saldo e como devo investir?"}
    ).json()
    assert data["status"] == "abstained"
    assert not data["calculations"]
    assert not provider.prompts
    orchestrator.research.run.assert_awaited_once()


def test_fabrica_nao_inicializa_rag_para_consulta_pessoal():
    orchestrator = get_orchestrator()
    assert orchestrator.research.rag_service is None


@pytest.mark.parametrize(
    ("message", "value"),
    [
        ("Quanto gastei na Loja D em novembro de 2026?", 100.0),
        ("Quanto gastei no Mercado Z em novembro de 2026?", 350.25),
    ],
)
def test_estabelecimento_especifico_nao_vira_ranking_ou_total_global(
    financial_session, message, value
):
    client, _, _, _ = financial_session
    data = client.post("/v1/agents/ask", json={"message": message}).json()
    assert data["status"] == "answered", data
    assert len(data["calculations"]) == 1
    assert data["calculations"][0]["value"] == pytest.approx(value)


@pytest.mark.parametrize(
    "message",
    [
        "Quanto gastei na Loja Desconhecida em novembro de 2026?",
        "Quanto gastei em Restaurante Desconhecido em novembro de 2026?",
    ],
)
def test_estabelecimento_ausente_nao_vira_ranking(financial_session, message):
    client, _, _, _ = financial_session
    data = client.post(
        "/v1/agents/ask",
        json={"message": message},
    ).json()
    assert data["status"] == "abstained", data
    assert not data["calculations"]


async def test_biblioteca_e_fonte_unica_e_snapshot_sobrevive_a_mutacao(financial_session):
    from unittest.mock import AsyncMock

    from app.domain.agents import AgentStep

    _, lib, _, orchestrator = financial_session

    async def mutate_library(ctx):
        lib.transactions.clear()
        lib.accounts.clear()
        lib.statements.clear()
        return AgentStep(
            agent=AgentName.RESEARCH, status=StepStatus.OK, summary="Pesquisa concluída."
        )

    orchestrator.research.run = AsyncMock(side_effect=mutate_library)
    response = await orchestrator.run(
        "Qual meu saldo e como organizar o orçamento?",
        library=lib,
        reference_date=date(2026, 11, 20),
    )
    assert response.status == "answered", response
    assert next(c.value for c in response.calculations if c.key == "total_expenses") == 2917.0


def test_contexto_financeiro_nao_e_serializado():
    from app.domain.agents import AgentContext, FinancialContext
    from app.domain.models import Account

    context = AgentContext(
        question="Saldo?",
        financial=FinancialContext(
            intent="summary",
            reference_date=date(2026, 11, 20),
            accounts={"segredo": Account(id="segredo", acct_id="conta-sigilosa")},
        ),
    )
    assert "financial" not in context.model_dump()
    assert "conta-sigilosa" not in context.model_dump_json()


@pytest.mark.parametrize(
    ("message", "filters", "key", "value"),
    [
        ("Qual minha próxima fatura pessoal do Nubank?", {}, "next_statement_installments", 100.0),
        ("Quanto devo em parcelas?", {}, "installments_remaining", 200.0),
        (
            "Quanto falta pagar da minha fatura fechada pessoal do Nubank?",
            {},
            "closed_statement_due",
            350.4,
        ),
        ("Quais minhas categorias em novembro de 2026?", {}, "top_category_1", 650.75),
    ],
)
def test_proximos_compromissos_e_ranking_completo(financial_session, message, filters, key, value):
    client, _, _, _ = financial_session
    data = client.post("/v1/agents/ask", json={"message": message, **filters}).json()
    assert data["status"] == "answered", data
    assert next(c["value"] for c in data["calculations"] if c["key"] == key) == pytest.approx(value)


@pytest.mark.parametrize(
    ("message", "filters", "fragment"),
    [
        ("Quanto gastei em outubro e novembro de 2026?", {}, "mais de um período"),
        ("Qual minha fatura?", {}, "aberta"),
        ("Quais minhas dívidas em outubro de 2026?", {}, "retrato"),
        ("Quais minhas categorias na fatura aberta?", {}, "intervalo de datas"),
        ("Quanto gastei?", {"account_id": CC, "period": "proxima_fatura"}, "cartão importado"),
        ("Quanto gastei?", {"period": "fevereiro de 0000"}, "inválida"),
        ("Quanto gastei em fevereiro de 0000?", {}, "inválidas"),
        ("Quanto gastei nas contas pessoais e da empresa?", {}, "pessoais"),
    ],
)
def test_recortes_incompativeis_pedem_esclarecimento(financial_session, message, filters, fragment):
    client, _, provider, _ = financial_session
    data = client.post("/v1/agents/ask", json={"message": message, **filters}).json()
    assert data["status"] == "abstained", data
    assert not data["calculations"]
    assert fragment in data["answer"].lower()
    assert not provider.prompts


def test_revisao_pode_corrigir_numero_inventado_sem_bloqueio_obsoleto(financial_session):
    client, _, _, orchestrator = financial_session

    class CorrectingLLM(GroundedMockLLM):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(content="Seu saldo é R$ 999,99.", model="mock")
            return await super().generate(**kwargs)

    provider = CorrectingLLM()
    orchestrator.communication = CommunicationAgent(provider)
    data = client.post("/v1/agents/ask", json={"message": "Qual meu saldo?"}).json()
    assert provider.calls == 2
    assert data["status"] == "answered", data
    assert not data["validation_issues"]
    assert "999,99" not in data["answer"]
