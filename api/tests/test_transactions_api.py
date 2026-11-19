import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers.v1 import transactions as transactions_router

# Extrato OFX fictício: 1 receita e 1 despesa (nenhum dado real).
OFX_SINTETICO = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS>
<DTSERVER>20261101<LANGUAGE>POR</SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>
<STMTRS><CURDEF>BRL
<BANKACCTFROM><BANKID>000<ACCTID>12345<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20261101<DTEND>20261130
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261101<TRNAMT>5000.00<FITID>1
<MEMO>SALARIO SINTETICO</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261103<TRNAMT>-342.80<FITID>2
<MEMO>SUPERMERCADO SINTETICO</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>4657.20<DTASOF>20261130</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""


@pytest.fixture(autouse=True)
def memoria_limpa():
    transactions_router._LOCAL_TRANSACTIONS.clear()
    yield
    transactions_router._LOCAL_TRANSACTIONS.clear()


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _enviar(client: AsyncClient, nome: str = "extrato.ofx", conteudo: bytes = OFX_SINTETICO):
    return await client.post("/v1/transactions/upload", files={"file": (nome, conteudo)})


@pytest.mark.asyncio
async def test_upload_ofx_atualiza_o_resumo_calculado_no_backend():
    async with _cliente() as client:
        resposta = await _enviar(client)
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["filename"] == "extrato.ofx"
        assert corpo["imported_count"] == 2
        assert corpo["duplicate_count"] == 0

        resumo = (await client.get("/v1/transactions/summary")).json()
        assert resumo["total_income"] == 5000.0
        assert resumo["total_expenses"] == 342.8
        assert resumo["net_balance"] == 4657.2
        assert resumo["transaction_count"] == 2


@pytest.mark.asyncio
async def test_reenviar_o_mesmo_extrato_nao_conta_duas_vezes():
    async with _cliente() as client:
        await _enviar(client)
        segunda = (await _enviar(client, nome="extrato_de_novo.ofx")).json()
        assert segunda["duplicate_count"] == 2

        resumo = (await client.get("/v1/transactions/summary")).json()
        assert resumo["total_income"] == 5000.0
        assert resumo["total_expenses"] == 342.8

        lancamentos = (await client.get("/v1/transactions")).json()
        origem = {(t["source_file"], t["is_duplicate"]) for t in lancamentos}
        assert origem == {("extrato.ofx", False), ("extrato_de_novo.ofx", True)}


@pytest.mark.asyncio
async def test_formato_nao_suportado_devolve_400_com_mensagem():
    async with _cliente() as client:
        resposta = await _enviar(client, nome="extrato.txt", conteudo=b"qualquer coisa")
        assert resposta.status_code == 400
        assert ".ofx" in resposta.json()["detail"]


@pytest.mark.asyncio
async def test_upload_nubank_cartao_informa_banco_tipo_e_exclui_pagamento():
    from tests.nubank_samples import FATURA_PADRAO

    async with _cliente() as client:
        resposta = await _enviar(client, "Nubank_2026-12-10.ofx", FATURA_PADRAO)
        corpo = resposta.json()
        assert resposta.status_code == 200
        assert corpo["institution"] == "nubank"
        assert corpo["kind"] == "cartao"
        assert corpo["ledger_balance"] == -250.0
        assert corpo["by_nature"]["pagamento_fatura"] == 1
        assert corpo["summary"]["excluded_count"] == 1
        assert corpo["summary"]["total_income"] == 0


@pytest.mark.asyncio
async def test_reenvio_do_mesmo_arquivo_nubank_nao_altera_totais():
    from tests.nubank_samples import EXTRATO_PADRAO

    async with _cliente() as client:
        primeiro = (await _enviar(client, "e.ofx", EXTRATO_PADRAO)).json()
        segundo = (await _enviar(client, "e.ofx", EXTRATO_PADRAO)).json()
        assert segundo["duplicate_count"] == segundo["imported_count"]
        assert segundo["summary"]["total_expenses"] == primeiro["summary"]["total_expenses"]
        assert segundo["summary"]["total_income"] == primeiro["summary"]["total_income"]


@pytest.mark.asyncio
async def test_upload_de_arquivo_invalido_e_formato_nao_suportado():
    async with _cliente() as client:
        assert (await _enviar(client, "x.ofx", b"lixo")).status_code == 400
        assert (await _enviar(client, "x.csv", b"a,b")).status_code == 400
