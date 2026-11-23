"""Retrato da biblioteca entre o aparelho e a API (ADR 0025). Dados sintéticos."""

from app.services.library_service import LIBRARY
from tests.helpers_api import cliente, enviar
from tests.test_transactions_api import OFX_SINTETICO


async def test_app_hidrata_a_api_vazia_com_o_retrato_do_aparelho():
    async with cliente() as client:
        await enviar(client, OFX_SINTETICO, "extrato.ofx", owner="pessoal")
        retrato = (await client.get("/v1/library/snapshot")).json()
        assert len(retrato["transactions"]) == 2

        # "API reiniciada": memória vazia; o app devolve o que guardou no aparelho
        LIBRARY.reset()
        assert (await client.get("/v1/transactions")).json() == []
        resposta = await client.put("/v1/library/snapshot", json=retrato)
        assert resposta.status_code == 200
        assert resposta.json()["transactions_total"] == 2

        resumo = (await client.get("/v1/transactions/summary")).json()
        assert resumo["total_income"] == 5000.0
        contas = (await client.get("/v1/accounts")).json()
        assert contas[0]["owner"] == "pessoal"


async def test_retrato_carrega_decisoes_do_usuario():
    async with cliente() as client:
        await enviar(client, OFX_SINTETICO, "extrato.ofx", owner="empresa")
        retrato = (await client.get("/v1/library/snapshot")).json()
        LIBRARY.reset()
        await client.put("/v1/library/snapshot", json=retrato)
        volta = (await client.get("/v1/library/snapshot")).json()
    assert volta["accounts"] == retrato["accounts"]
    assert volta["statements"] == retrato["statements"]


async def test_substituir_apaga_o_que_a_api_tinha():
    async with cliente() as client:
        await enviar(client, OFX_SINTETICO, "extrato.ofx")
        vazio = {"version": 1}
        await client.put("/v1/library/snapshot", json=vazio)
        assert (await client.get("/v1/transactions")).json() == []


async def test_retrato_de_versao_invalida_e_recusado():
    async with cliente() as client:
        resposta = await client.put("/v1/library/snapshot", json={"transactions": "x"})
    assert resposta.status_code == 422
