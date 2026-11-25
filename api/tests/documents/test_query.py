from unittest.mock import AsyncMock

import pytest

from app.domain.agents import AgentName, StepStatus
from app.domain.models import TransactionNature
from app.services.agent_query_service import AgentQueryService
from app.services.agents.orchestrator import Orchestrator
from app.services.agents.validation import ValidationAgent
from app.services.library_service import LIBRARY


@pytest.fixture
def orchestrator():
    return Orchestrator(AsyncMock(), AsyncMock(), AsyncMock(), ValidationAgent())


@pytest.mark.parametrize(
    "question", ["Quanto gastei nessa loja?", "Quanto gastei na PADARIA SINTETICA?"]
)
async def test_consulta_local_cita_lancamento_e_passa_pela_validacao(
    client, reviewed, orchestrator, question
):
    uid = (await client.post("/v1/documents/confirm", json=reviewed)).json()["uid"]
    response = await AgentQueryService(orchestrator).run(question, LIBRARY.transactions, uid)
    assert response.status == "answered"
    assert response.calculations[0].value == 12.5
    assert uid in response.answer
    assert "R$ 12,50" in response.answer
    assert response.evidences[0].source_name == "Biblioteca local"
    assert [step.agent for step in response.steps] == [AgentName.ANALYSIS, AgentName.VALIDATION]
    assert response.steps[-1].status == StepStatus.OK
    assert response.total_ms > 0
    orchestrator.research.run.assert_not_called()
    orchestrator.communication.run.assert_not_called()


async def test_consulta_exclui_duplicatas_e_transferencias_proprias(client, reviewed, orchestrator):
    uid = (await client.post("/v1/documents/confirm", json=reviewed)).json()["uid"]
    tx = LIBRARY.transactions[0]
    transactions = [
        tx,
        tx.model_copy(update={"is_duplicate": True}),
        tx.model_copy(update={"nature": TransactionNature.INTERNAL_TRANSFER}),
    ]
    response = await AgentQueryService(orchestrator).run(
        "Quanto gastei nessa loja?", transactions, uid
    )
    assert response.calculations[0].value == 12.5
    assert response.steps[0].detail["transaction_uids"] == [uid]


@pytest.mark.parametrize("uid", [None, "000000000000"])
async def test_referencia_ausente_ou_desconhecida_pede_esclarecimento(
    client, reviewed, orchestrator, uid
):
    await client.post("/v1/documents/confirm", json=reviewed)
    response = await AgentQueryService(orchestrator).run(
        "Quanto gastei nessa loja?", LIBRARY.transactions, uid
    )
    assert response.status == "abstained"
    assert "Informe o documento" in response.answer
    assert not response.calculations
    orchestrator.research.run.assert_not_called()


async def test_bloqueio_da_validacao_retem_resposta_local(client, reviewed, orchestrator):
    uid = (await client.post("/v1/documents/confirm", json=reviewed)).json()["uid"]
    original = orchestrator.validation.run

    async def reject(ctx):
        ctx.draft_answer = "Gasto no estabelecimento: R$ 999,99. [1]"
        return await original(ctx)

    orchestrator.validation.run = reject
    response = await AgentQueryService(orchestrator).run(
        "Quanto gastei nessa loja?", LIBRARY.transactions, uid
    )
    assert response.status == "rejected"
    assert "999,99" not in response.answer
    assert any(issue.code == "NUMBER_NOT_SUPPORTED" for issue in response.validation_issues)


async def test_pergunta_educacional_continua_no_orquestrador(orchestrator):
    orchestrator.run = AsyncMock(return_value="resposta do fluxo geral")
    result = await AgentQueryService(orchestrator).run("Como montar uma reserva?", [])
    assert result == "resposta do fluxo geral"
    orchestrator.run.assert_awaited_once_with("Como montar uma reserva?", transactions=[])


async def test_valor_com_milhar_preserva_validacao_e_formato_pt_br(client, reviewed, orchestrator):
    reviewed["amount"] = "6000.50"
    uid = (await client.post("/v1/documents/confirm", json=reviewed)).json()["uid"]
    response = await AgentQueryService(orchestrator).run(
        "Quanto gastei nessa loja?", LIBRARY.transactions, uid
    )
    assert response.status == "answered"
    assert response.calculations[0].value == 6000.5
    assert "R$ 6.000,50" in response.answer


async def test_nome_curto_do_estabelecimento_pode_ser_consultado(client, reviewed, orchestrator):
    reviewed["description"] = "BP"
    uid = (await client.post("/v1/documents/confirm", json=reviewed)).json()["uid"]
    response = await AgentQueryService(orchestrator).run(
        "Quanto gastei na BP?", LIBRARY.transactions
    )
    assert response.status == "answered"
    assert uid in response.answer


@pytest.mark.parametrize("question", ["Quanto gastei em janeiro?", "Quanto gastei em alimentação?"])
async def test_pergunta_que_nao_e_de_loja_segue_para_o_orquestrador(
    client, reviewed, orchestrator, question
):
    await client.post("/v1/documents/confirm", json=reviewed)
    esperado = object()
    orchestrator.run = AsyncMock(return_value=esperado)
    resposta = await AgentQueryService(orchestrator).run(question, LIBRARY.transactions)
    assert resposta is esperado


async def test_total_soma_so_documentos_do_estabelecimento(client, reviewed, orchestrator):
    uid = (await client.post("/v1/documents/confirm", json=reviewed)).json()["uid"]
    importado = LIBRARY.transactions[0].model_copy(
        update={"origin": "importacao", "amount": 100.0, "id": "ofx:1"}
    )
    resposta = await AgentQueryService(orchestrator).run(
        "Quanto gastei nessa loja?", [*LIBRARY.transactions, importado], uid
    )
    assert resposta.calculations[0].value == 12.5
