import pytest

from tests.bb_samples import pdf_de_linhas
from tests.helpers_api import cliente, enviar
from tests.nubank_samples import (
    CARTAO_PF,
    CARTAO_PJ,
    CONTA_PF,
    CONTA_PJ,
    extrato_conta,
    fatura_cartao,
    lancamento,
)

D = lancamento
NOME_PF = "NU_000000000_01OUT2026_31OUT2026.ofx"
NOME_PJ = "6a20b244-bf06-47fb-9f05-e3735a88483c-2026-10-01-2026-10-31.ofx"
PIX_PARA_PJ = (
    "Transferência enviada pelo Pix - EMPRESA FICTICIA LTDA. - 11.111.111/0001-11 - "
    "NU PAGAMENTOS S.A. (0260) Agência: 1 Conta: 1111111-1"
)
PIX_PARA_PF = (
    "Transferência enviada pelo Pix - Maria Exemplo da Silva - •••.123.456-•• - "
    "NU PAGAMENTOS S.A. (0260) Agência: 1 Conta: 0000000-0"
)


async def inspecionar(c, conteudo, nome="a.ofx", owner=None, expect_kind=None):
    data = {}
    if owner:
        data["owner"] = owner
    if expect_kind:
        data["expect_kind"] = expect_kind
    return await c.post("/v1/transactions/inspect", files={"file": (nome, conteudo)}, data=data)


def _codigos(corpo):
    return {w["code"] for w in corpo["warnings"]}


@pytest.mark.asyncio
async def test_inspecionar_nao_altera_nada():
    arquivo = extrato_conta([D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")])
    async with cliente() as c:
        corpo = (await inspecionar(c, arquivo)).json()
        assert corpo["institution"] == "nubank" and corpo["kind"] == "conta"
        assert corpo["transaction_count"] == 1
        assert (await c.get("/v1/transactions")).json() == []
        assert (await c.get("/v1/accounts")).json() == []


@pytest.mark.asyncio
async def test_conta_empresas_enviada_como_pessoal_e_barrada_pelo_cadastro():
    pj = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], acct=CONTA_PJ
    )
    async with cliente() as c:
        await enviar(c, pj, NOME_PJ, owner="empresa")
        insp = (await inspecionar(c, pj, NOME_PJ, owner="pessoal")).json()
        assert insp["has_conflict"] is True
        assert "dono_diferente_do_detectado" in _codigos(insp)
        assert insp["detected_owner"] == "empresa" and insp["confidence"] == "alta"
        recusa = await enviar(c, pj, NOME_PJ, owner="pessoal")
        assert recusa.status_code == 409
        assert "Nubank Empresas" in recusa.json()["detail"]
        # o usuário confirma que quer mudar: importa e passa a valer o dono confirmado
        ok = await c.post(
            "/v1/transactions/upload",
            files={"file": (NOME_PJ, pj)},
            data={"owner": "pessoal", "confirmed": "true"},
        )
        assert ok.status_code == 200
        assert ok.json()["account"]["owner"] == "pessoal"


@pytest.mark.asyncio
async def test_mesma_conta_com_o_dono_certo_nao_gera_aviso():
    pj = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], acct=CONTA_PJ
    )
    async with cliente() as c:
        await enviar(c, pj, NOME_PJ, owner="empresa")
        insp = (await inspecionar(c, pj, NOME_PJ, owner="empresa")).json()
    assert insp["warnings"] == []
    assert insp["known_owner"] == "empresa"


@pytest.mark.asyncio
async def test_nome_do_arquivo_do_empresas_com_dono_pessoal_gera_atencao_sem_bloquear():
    arquivo = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], acct=CONTA_PJ
    )
    async with cliente() as c:
        insp = (await inspecionar(c, arquivo, NOME_PJ, owner="pessoal")).json()
        assert insp["detected_owner"] == "empresa" and insp["confidence"] == "media"
        aviso = next(w for w in insp["warnings"] if w["code"] == "dono_diferente_do_detectado")
        assert aviso["severity"] == "atencao"
        assert insp["has_conflict"] is False
        # não bloqueia o upload
        assert (await enviar(c, arquivo, NOME_PJ, owner="pessoal")).status_code == 200


@pytest.mark.asyncio
async def test_nome_do_arquivo_pessoal_com_dono_empresas_gera_atencao():
    arquivo = extrato_conta([D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")])
    async with cliente() as c:
        insp = (await inspecionar(c, arquivo, NOME_PF, owner="empresa")).json()
    assert insp["detected_owner"] == "pessoal"
    assert "dono_diferente_do_detectado" in _codigos(insp)


@pytest.mark.asyncio
async def test_sem_dono_escolhido_o_detector_sugere_pelo_nome_do_arquivo():
    arquivo = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], acct=CONTA_PJ
    )
    async with cliente() as c:
        insp = (await inspecionar(c, arquivo, NOME_PJ)).json()
    assert insp["detected_owner"] == "empresa"
    assert insp["needs_owner"] is False
    assert insp["signals"][0]["source"] == "nome_do_arquivo"


@pytest.mark.asyncio
async def test_sem_nenhum_sinal_pergunta_o_dono():
    arquivo = extrato_conta([D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")])
    async with cliente() as c:
        insp = (await inspecionar(c, arquivo, "extrato.ofx")).json()
    assert insp["detected_owner"] is None and insp["needs_owner"] is True


@pytest.mark.asyncio
async def test_documentos_de_outros_arquivos_revelam_que_a_conta_e_empresa():
    pf = extrato_conta([D("DEBIT", "20261005", "-308.76", "p1", PIX_PARA_PJ)], acct=CONTA_PF)
    pj = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], acct=CONTA_PJ
    )
    async with cliente() as c:
        await enviar(c, pf, "extrato.ofx", owner="pessoal")
        # o Pix do pessoal citou a conta 1111111-1 com CNPJ: essa conta é de uma empresa
        errado = (await inspecionar(c, pj, "extrato.ofx", owner="pessoal")).json()
        assert errado["has_conflict"] is True
        assert errado["signals"][0]["source"] == "documentos"
        certo = (await inspecionar(c, pj, "extrato.ofx", owner="empresa")).json()
    assert certo["warnings"] == [] and certo["detected_owner"] == "empresa"


@pytest.mark.asyncio
async def test_documentos_de_outros_arquivos_revelam_que_a_conta_e_pessoal():
    pj = extrato_conta([D("DEBIT", "20261005", "-295.02", "j1", PIX_PARA_PF)], acct=CONTA_PJ)
    pf = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], acct=CONTA_PF
    )
    async with cliente() as c:
        await enviar(c, pj, "extrato.ofx", owner="empresa")
        insp = (await inspecionar(c, pf, "extrato.ofx", owner="empresa")).json()
    assert insp["has_conflict"] is True and insp["detected_owner"] == "pessoal"


@pytest.mark.asyncio
async def test_fatura_do_cartao_da_empresa_enviada_como_pessoal_pelo_pagamento_da_fatura():
    conta_pj = extrato_conta(
        [
            D("DEBIT", "20261111", "-80.00", "k1", "Pagamento de fatura"),
            D("DEBIT", "20261211", "-120.00", "k2", "Pagamento de fatura"),
        ],
        acct=CONTA_PJ,
        inicio="20261101",
        fim="20261231",
        gerado="20270105",
    )
    cartao_pj = fatura_cartao(
        [
            D("CREDIT", "20261110", "80.00", "c1", "Pagamento recebido"),
            D("CREDIT", "20261210", "120.00", "c2", "Pagamento recebido"),
        ],
        acct=CARTAO_PJ,
        inicio="20261011",
        fim="20261211",
        gerado="20270105",
    )
    async with cliente() as c:
        await enviar(c, conta_pj, NOME_PJ, owner="empresa")
        insp = (await inspecionar(c, cartao_pj, "Nubank_2026-12-18.ofx", owner="pessoal")).json()
        assert insp["has_conflict"] is True  # dois pagamentos batem: confiança alta
        assert insp["signals"][0]["source"] == "pagamento_da_fatura"
        assert (
            await enviar(c, cartao_pj, "Nubank_2026-12-18.ofx", owner="pessoal")
        ).status_code == 409
        certo = (await inspecionar(c, cartao_pj, "Nubank_2026-12-18.ofx", owner="empresa")).json()
    assert certo["warnings"] == []


@pytest.mark.asyncio
async def test_um_so_pagamento_batendo_e_apenas_atencao():
    conta_pj = extrato_conta(
        [D("DEBIT", "20261111", "-80.00", "k1", "Pagamento de fatura")],
        acct=CONTA_PJ,
        gerado="20261201",
        inicio="20261101",
        fim="20261130",
    )
    cartao = fatura_cartao(
        [D("CREDIT", "20261110", "80.00", "c1", "Pagamento recebido")],
        acct=CARTAO_PJ,
        gerado="20261201",
    )
    async with cliente() as c:
        await enviar(c, conta_pj, NOME_PJ, owner="empresa")
        insp = (await inspecionar(c, cartao, "Nubank_2026-12-18.ofx", owner="pessoal")).json()
    assert insp["has_conflict"] is False
    assert insp["confidence"] == "media"
    assert "dono_diferente_do_detectado" in _codigos(insp)


@pytest.mark.asyncio
async def test_extrato_da_conta_que_pagou_o_cartao_pessoal_nao_e_empresas():
    cartao_pf = fatura_cartao(
        [
            D("CREDIT", "20261110", "80.00", "c1", "Pagamento recebido"),
            D("CREDIT", "20261210", "120.00", "c2", "Pagamento recebido"),
        ],
        acct=CARTAO_PF,
        inicio="20261011",
        fim="20261211",
        gerado="20270105",
    )
    conta = extrato_conta(
        [
            D("DEBIT", "20261111", "-80.00", "k1", "Pagamento de fatura"),
            D("DEBIT", "20261211", "-120.00", "k2", "Pagamento de fatura"),
        ],
        acct=CONTA_PF,
        inicio="20261101",
        fim="20261231",
        gerado="20270105",
    )
    async with cliente() as c:
        await enviar(c, cartao_pf, "Nubank_2026-12-18.ofx", owner="pessoal")
        insp = (await inspecionar(c, conta, "extrato.ofx", owner="empresa")).json()
    assert insp["has_conflict"] is True and insp["detected_owner"] == "pessoal"


@pytest.mark.asyncio
async def test_tipo_escolhido_diferente_do_arquivo():
    cartao = fatura_cartao([D("DEBIT", "20261105", "-10.00", "a1", "Loja X")], gerado="20261210")
    conta = extrato_conta([D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")])
    async with cliente() as c:
        a = (await inspecionar(c, cartao, expect_kind="conta")).json()
        b = (await inspecionar(c, conta, expect_kind="cartao")).json()
        assert a["has_conflict"] and "tipo_diferente" in _codigos(a)
        assert "fatura do cartão" in a["warnings"][0]["message"]
        assert b["has_conflict"] and "extrato de conta" in b["warnings"][0]["message"]
        assert (await inspecionar(c, cartao, expect_kind="cartao")).json()["warnings"] == []
        assert (await enviar_com_tipo(c, cartao, "conta")).status_code == 409


async def enviar_com_tipo(c, conteudo, tipo, confirmed=False):
    data = {"expect_kind": tipo}
    if confirmed:
        data["confirmed"] = "true"
    return await c.post("/v1/transactions/upload", files={"file": ("a.ofx", conteudo)}, data=data)


@pytest.mark.asyncio
async def test_confirmar_tipo_diferente_importa_mesmo_assim():
    cartao = fatura_cartao([D("DEBIT", "20261105", "-10.00", "a1", "Loja X")], gerado="20261210")
    async with cliente() as c:
        r = await enviar_com_tipo(c, cartao, "conta", confirmed=True)
    assert r.status_code == 200 and r.json()["kind"] == "cartao"


@pytest.mark.asyncio
async def test_arquivo_ja_importado_em_outra_conta():
    lancs = [
        D("DEBIT", "20261012", "-5.00", "z1", "Compra no débito - A"),
        D("DEBIT", "20261013", "-6.00", "z2", "Compra no débito - B"),
        D("DEBIT", "20261014", "-7.00", "z3", "Compra no débito - C"),
    ]
    async with cliente() as c:
        await enviar(c, extrato_conta(lancs, acct=CONTA_PF), NOME_PF, owner="pessoal")
        insp = (
            await inspecionar(c, extrato_conta(lancs, acct=CONTA_PJ), NOME_PJ, owner="empresa")
        ).json()
    assert "ja_importado_em_outra_conta" in _codigos(insp)


@pytest.mark.asyncio
async def test_sinais_divergentes_baixam_a_confianca():
    pj = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], acct=CONTA_PJ
    )
    async with cliente() as c:
        await enviar(c, pj, NOME_PJ, owner="empresa")
        # mesma conta (cadastrada como empresa), mas com nome de arquivo do padrão pessoal
        insp = (await inspecionar(c, pj, NOME_PF, owner="empresa")).json()
    assert "sinais_divergentes" in _codigos(insp)
    assert insp["confidence"] == "baixa"


@pytest.mark.asyncio
async def test_banco_desconhecido_e_arquivo_vazio_sao_apenas_informativos():
    generico = (
        extrato_conta([])
        .replace(b"NU PAGAMENTOS S.A.", b"BANCO QUALQUER")
        .replace(b"<FID>260", b"<FID>999")
        .replace(b"<BANKID>0260", b"<BANKID>0999")
    )
    async with cliente() as c:
        insp = (await inspecionar(c, generico)).json()
    assert _codigos(insp) == {"banco_sem_perfil", "arquivo_vazio"}
    assert {w["severity"] for w in insp["warnings"]} == {"info"}
    assert insp["has_conflict"] is False


@pytest.mark.asyncio
async def test_pre_visualizacao_do_periodo_e_da_situacao():
    arquivo = fatura_cartao(
        [D("DEBIT", "20261105", "-10.00", "a1", "Loja X")],
        inicio="20261103",
        fim="20261203",
        gerado="20261118",
    )
    async with cliente() as c:
        insp = (await inspecionar(c, arquivo, "Nubank_2026-12-10.ofx")).json()
    assert insp["period"]["status"] == "aberta"
    assert insp["period"]["closes_on"] == "2026-12-03"


@pytest.mark.asyncio
async def test_parametros_invalidos_e_arquivo_que_nao_e_ofx():
    async with cliente() as c:
        assert (await inspecionar(c, b"lixo", "x.ofx")).status_code == 400
        arquivo = extrato_conta([])
        assert (await inspecionar(c, arquivo, owner="xyz")).status_code == 400
        assert (await inspecionar(c, arquivo, expect_kind="xyz")).status_code == 400
        assert (await inspecionar(c, b"%PDF", "fatura.pdf")).status_code == 400
        sem_perfil = pdf_de_linhas(["EXTRATO QUALQUER", "05/11 LOJA -R$ 10,00"])
        pdf = (await inspecionar(c, sem_perfil, "fatura.pdf")).json()
    assert pdf["warnings"] == [] and pdf["institution"] is None
