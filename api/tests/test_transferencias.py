import pytest

from app.services.transfer_service import name_matches
from tests.helpers_api import cliente, enviar
from tests.nubank_samples import CONTA_PF, CONTA_PJ, extrato_conta, lancamento

D = lancamento
ENVIADO_PJ = (
    "Transferência enviada pelo Pix - EMPRESA FICTICIA LTDA. - 11.111.111/0001-11 - "
    "NU PAGAMENTOS S.A."
)
RECEBIDO_PF = (
    "Transferência recebida pelo Pix - Maria Exemplo da Silva - •••.123.456-•• - NU PAGAMENTOS S.A."
)
ENVIADO_PF = (
    "Transferência enviada pelo Pix - Maria Exemplo da Silva - •••.123.456-•• - NU PAGAMENTOS S.A."
)
RECEBIDO_PJ = (
    "Transferência recebida pelo Pix - EMPRESA FICTICIA LTDA. - 11.111.111/0001-11 - "
    "NU PAGAMENTOS S.A."
)


# Pix com a conta de destino no texto (como no OFX real do Nubank): ligam as contas com certeza.
ENVIADO_PJ_CONTA = ENVIADO_PJ.replace(
    "NU PAGAMENTOS S.A.", "NU PAGAMENTOS S.A. (0260) Agência: 1 Conta: 1111111-1"
)
RECEBIDO_PF_CONTA = RECEBIDO_PF.replace(
    "NU PAGAMENTOS S.A.", "NU PAGAMENTOS S.A. (0260) Agência: 1 Conta: 0000000-0"
)


def _pf(lancamentos):
    return extrato_conta(lancamentos, acct=CONTA_PF)


def _pj(lancamentos):
    return extrato_conta(lancamentos, acct=CONTA_PJ)


async def _importar_par(c, dia_debito="20261005", dia_credito="20261005", valor="308.76"):
    await enviar(
        c, _pf([D("DEBIT", dia_debito, f"-{valor}", "p1", ENVIADO_PJ)]), "pf.ofx", "pessoal"
    )
    await enviar(c, _pj([D("CREDIT", dia_credito, valor, "j1", RECEBIDO_PF)]), "pj.ofx", "empresa")


@pytest.mark.asyncio
async def test_par_unico_entre_pessoal_e_empresas_e_sugerido_com_confianca_alta():
    async with cliente() as c:
        await _importar_par(c)
        sugestoes = (await c.get("/v1/transfers/suggestions")).json()
    assert len(sugestoes) == 1
    s = sugestoes[0]
    assert s["confidence"] == "alta" and s["amount"] == 308.76
    assert s["from_label"] == "Nubank · conta" and s["to_label"] == "Nubank Empresas · conta"


@pytest.mark.asyncio
async def test_upload_informa_quantas_transferencias_foram_sugeridas():
    async with cliente() as c:
        await enviar(c, _pf([D("DEBIT", "20261005", "-10.00", "p1", ENVIADO_PJ)]), "pf.ofx")
        corpo = (
            await enviar(c, _pj([D("CREDIT", "20261005", "10.00", "j1", RECEBIDO_PF)]), "pj.ofx")
        ).json()
    assert corpo["transfer_suggestions"] == 1


@pytest.mark.asyncio
async def test_um_dia_de_diferenca_ainda_e_sugerido_dois_dias_nao():
    async with cliente() as c:
        await _importar_par(c, "20261005", "20261006")
        assert len((await c.get("/v1/transfers/suggestions")).json()) == 1
    async with cliente() as c:
        await c.delete("/v1/transactions/clear")
        await _importar_par(c, "20261005", "20261007")
        assert (await c.get("/v1/transfers/suggestions")).json() == []


@pytest.mark.asyncio
async def test_valor_diferente_ou_mesma_conta_nao_geram_sugestao():
    async with cliente() as c:
        await enviar(c, _pf([D("DEBIT", "20261005", "-10.00", "p1", ENVIADO_PJ)]), "pf.ofx")
        await enviar(c, _pj([D("CREDIT", "20261005", "10.01", "j1", RECEBIDO_PF)]), "pj.ofx")
        assert (await c.get("/v1/transfers/suggestions")).json() == []
    async with cliente() as c:
        await c.delete("/v1/transactions/clear")
        # saída e entrada na MESMA conta (ex.: ida e volta): não é transferência entre contas
        await enviar(
            c,
            _pf(
                [
                    D("DEBIT", "20261005", "-10.00", "p1", ENVIADO_PJ),
                    D("CREDIT", "20261005", "10.00", "p2", RECEBIDO_PF),
                ]
            ),
            "pf.ofx",
        )
        assert (await c.get("/v1/transfers/suggestions")).json() == []


@pytest.mark.asyncio
async def test_varias_combinacoes_possiveis_ficam_com_confianca_media():
    async with cliente() as c:
        await enviar(c, _pf([D("DEBIT", "20261005", "-50.00", "p1", ENVIADO_PJ)]), "pf.ofx")
        await enviar(
            c,
            _pj(
                [
                    D("CREDIT", "20261005", "50.00", "j1", RECEBIDO_PF),
                    D("CREDIT", "20261005", "50.00", "j2", RECEBIDO_PF.replace("Maria", "Joana")),
                ]
            ),
            "pj.ofx",
        )
        sugestoes = (await c.get("/v1/transfers/suggestions")).json()
    assert len(sugestoes) == 2
    assert {s["confidence"] for s in sugestoes} == {"media"}


async def _confirmar(c):
    s = (await c.get("/v1/transfers/suggestions")).json()[0]
    return await c.post(
        "/v1/transfers/confirm", json={"debit_uid": s["debit_uid"], "credit_uid": s["credit_uid"]}
    )


@pytest.mark.asyncio
async def test_confirmar_tira_as_duas_pontas_dos_totais():
    async with cliente() as c:
        await _importar_par(c)
        antes = (await c.get("/v1/transactions/summary")).json()
        assert antes["total_expenses"] == 308.76 and antes["total_income"] == 308.76
        assert (await _confirmar(c)).status_code == 200
        depois = (await c.get("/v1/transactions/summary")).json()
        assert depois["total_expenses"] == 0 and depois["total_income"] == 0
        assert depois["excluded_count"] == 2
        assert (await c.get("/v1/transfers/suggestions")).json() == []
        confirmadas = (await c.get("/v1/transfers")).json()
    assert len(confirmadas) == 1 and confirmadas[0]["amount"] == 308.76


@pytest.mark.asyncio
async def test_identidade_confirmada_vale_mesmo_com_um_lado_so():
    async with cliente() as c:
        await _importar_par(c)
        await _confirmar(c)
        # Outro Pix para a mesma empresa (que é do usuário), sem a ponta de entrada importada.
        corpo = (
            await enviar(
                c,
                _pf([D("DEBIT", "20261010", "-77.00", "p9", ENVIADO_PJ)]),
                "pf2.ofx",
            )
        ).json()
        assert corpo["auto_transfers"] == 1
        resumo = (await c.get("/v1/transactions/summary")).json()
    assert resumo["total_expenses"] == 0


@pytest.mark.asyncio
async def test_identidade_vale_retroativamente_para_o_que_ja_estava_importado():
    async with cliente() as c:
        await enviar(
            c,
            _pf(
                [
                    D("DEBIT", "20261005", "-308.76", "p1", ENVIADO_PJ),
                    D("DEBIT", "20261020", "-40.00", "p2", ENVIADO_PJ),
                ]
            ),
            "pf.ofx",
        )
        await enviar(c, _pj([D("CREDIT", "20261005", "308.76", "j1", RECEBIDO_PF)]), "pj.ofx")
        await _confirmar(c)
        resumo = (await c.get("/v1/transactions/summary")).json()
    assert resumo["total_expenses"] == 0  # o Pix de 40 também era para a própria empresa


@pytest.mark.asyncio
async def test_documento_igual_reconhece_a_conta_mesmo_com_o_nome_diferente():
    async with cliente() as c:
        await _importar_par(c)
        await _confirmar(c)
        outro_nome = ENVIADO_PJ.replace("EMPRESA FICTICIA LTDA.", "VHLS SERVICOS DIGITAIS")
        corpo = (
            await enviar(c, _pf([D("DEBIT", "20261011", "-5.00", "p8", outro_nome)]), "pf3.ofx")
        ).json()
    assert corpo["auto_transfers"] == 1


@pytest.mark.asyncio
async def test_pix_para_terceiro_continua_como_despesa():
    async with cliente() as c:
        await _importar_par(c)
        await _confirmar(c)
        terceiro = ENVIADO_PJ.replace("EMPRESA FICTICIA LTDA.", "PADARIA OUTRA LTDA.").replace(
            "11.111.111/0001-11", "22.222.222/0001-22"
        )
        corpo = (
            await enviar(c, _pf([D("DEBIT", "20261012", "-9.00", "p7", terceiro)]), "pf4.ofx")
        ).json()
        assert corpo["auto_transfers"] == 0
        assert corpo["summary"]["total_expenses"] == 9.0


@pytest.mark.asyncio
async def test_rejeitar_nao_sugere_de_novo_nem_depois_de_reimportar():
    async with cliente() as c:
        await _importar_par(c)
        s = (await c.get("/v1/transfers/suggestions")).json()[0]
        r = await c.post(
            "/v1/transfers/reject",
            json={"debit_uid": s["debit_uid"], "credit_uid": s["credit_uid"]},
        )
        assert r.status_code == 200
        assert (await c.get("/v1/transfers/suggestions")).json() == []
        await _importar_par(c)  # reenvio dos mesmos arquivos
        assert (await c.get("/v1/transfers/suggestions")).json() == []
        resumo = (await c.get("/v1/transactions/summary")).json()
    assert resumo["total_expenses"] == 308.76  # continua como despesa


@pytest.mark.asyncio
async def test_desfazer_devolve_os_lancamentos_e_a_sugestao():
    async with cliente() as c:
        await _importar_par(c)
        pid = (await _confirmar(c)).json()["id"]
        r = await c.post("/v1/transfers/undo", json={"id": pid})
        assert r.status_code == 200
        resumo = (await c.get("/v1/transactions/summary")).json()
        assert resumo["total_expenses"] == 308.76 and resumo["total_income"] == 308.76
        assert len((await c.get("/v1/transfers/suggestions")).json()) == 1
        assert (await c.post("/v1/transfers/undo", json={"id": "nada"})).status_code == 404


@pytest.mark.asyncio
async def test_confirmar_valida_os_lancamentos():
    async with cliente() as c:
        await _importar_par(c)
        s = (await c.get("/v1/transfers/suggestions")).json()[0]
        d, cr = s["debit_uid"], s["credit_uid"]
        assert (
            await c.post("/v1/transfers/confirm", json={"debit_uid": "x", "credit_uid": cr})
        ).status_code == 404
        # direções trocadas
        assert (
            await c.post("/v1/transfers/confirm", json={"debit_uid": cr, "credit_uid": d})
        ).status_code == 400


@pytest.mark.asyncio
async def test_confirmar_pontas_da_mesma_conta_e_recusado():
    async with cliente() as c:
        await enviar(
            c,
            _pf(
                [
                    D("DEBIT", "20261005", "-10.00", "p1", ENVIADO_PJ),
                    D("CREDIT", "20261005", "10.00", "p2", RECEBIDO_PF),
                ]
            ),
            "pf.ofx",
        )
        lista = (await c.get("/v1/transactions")).json()
        deb = next(t for t in lista if t["type"] == "debit")["uid"]
        cre = next(t for t in lista if t["type"] == "credit")["uid"]
        r = await c.post("/v1/transfers/confirm", json={"debit_uid": deb, "credit_uid": cre})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_transferencia_inversa_pj_para_pf():
    async with cliente() as c:
        await enviar(
            c, _pj([D("DEBIT", "20261008", "-295.02", "j2", ENVIADO_PF)]), "pj.ofx", "empresa"
        )
        await enviar(
            c, _pf([D("CREDIT", "20261008", "295.02", "p2", RECEBIDO_PJ)]), "pf.ofx", "pessoal"
        )
        s = (await c.get("/v1/transfers/suggestions")).json()
    assert len(s) == 1 and s[0]["from_label"] == "Nubank Empresas · conta"


def test_nomes_truncados_ou_com_as_mesmas_palavras_sao_o_mesmo():
    assert name_matches("Maria Exemplo da Silva", "MARIA EXEMPLO DA SILVA")
    assert name_matches("Victor Hugo Lima Schmid", "Victor Hugo Lima Schmidt")
    assert name_matches("Silva Maria Exemplo", "Maria Exemplo")
    assert not name_matches("Maria", "Maria")  # curto demais para ser identidade
    assert not name_matches("Maria Exemplo", "João Exemplo")
    assert not name_matches(None, "Maria Exemplo")
    assert not name_matches("", "")


# --- ligação automática pela conta de destino ---------------------------------------------


async def _importar_par_com_conta(c, primeiro="pf"):
    pf = _pf([D("DEBIT", "20261005", "-308.76", "p1", ENVIADO_PJ_CONTA)])
    pj = _pj([D("CREDIT", "20261005", "308.76", "j1", RECEBIDO_PF_CONTA)])
    ordem = [(pf, "pf.ofx", "pessoal"), (pj, "pj.ofx", "empresa")]
    if primeiro == "pj":
        ordem.reverse()
    for conteudo, nome, dono in ordem:
        await enviar(c, conteudo, nome, dono)


@pytest.mark.asyncio
@pytest.mark.parametrize("primeiro", ["pf", "pj"])
async def test_pix_para_outra_conta_importada_e_marcado_sozinho(primeiro):
    async with cliente() as c:
        await _importar_par_com_conta(c, primeiro)
        resumo = (await c.get("/v1/transactions/summary")).json()
        assert resumo["total_expenses"] == 0 and resumo["total_income"] == 0
        assert resumo["excluded_count"] == 2
        assert (await c.get("/v1/transfers/suggestions")).json() == []
        automaticas = (await c.get("/v1/transfers")).json()
    # As duas pontas (saída na PF e entrada na PJ) são a mesma transferência: um item só.
    assert len(automaticas) == 1
    assert automaticas[0]["kind"] == "automatica"
    assert automaticas[0]["amount"] == 308.76
    assert automaticas[0]["both_sides"] is True
    assert automaticas[0]["from_account"] == "nubank:0000000-0"
    assert automaticas[0]["to_account"] == "nubank:1111111-1"


@pytest.mark.asyncio
async def test_so_uma_conta_importada_nao_liga_nada():
    async with cliente() as c:
        corpo = (
            await enviar(
                c, _pf([D("DEBIT", "20261005", "-10.00", "p1", ENVIADO_PJ_CONTA)]), "pf.ofx"
            )
        ).json()
        assert corpo["auto_transfers"] == 0
        assert corpo["summary"]["total_expenses"] == 10.0


@pytest.mark.asyncio
async def test_banco_diferente_com_o_mesmo_numero_de_conta_nao_liga():
    outro_banco = ENVIADO_PJ_CONTA.replace("(0260)", "(0341)")
    async with cliente() as c:
        await enviar(c, _pf([D("DEBIT", "20261005", "-10.00", "p1", outro_banco)]), "pf.ofx")
        await enviar(c, _pj([D("CREDIT", "20261009", "1.00", "j1", RECEBIDO_PJ)]), "pj.ofx")
        assert (await c.get("/v1/transactions/summary")).json()["total_expenses"] == 10.0


@pytest.mark.asyncio
async def test_pix_para_a_propria_conta_nao_e_ligacao_entre_contas():
    para_si = ENVIADO_PJ.replace(
        "NU PAGAMENTOS S.A.", "NU PAGAMENTOS S.A. (0260) Agência: 1 Conta: 0000000-0"
    )
    async with cliente() as c:
        corpo = (
            await enviar(c, _pf([D("DEBIT", "20261005", "-10.00", "p1", para_si)]), "pf.ofx")
        ).json()
    assert corpo["auto_transfers"] == 0


@pytest.mark.asyncio
async def test_usuario_desfaz_a_marcacao_automatica_e_ela_continua_desfeita():
    async with cliente() as c:
        await _importar_par_com_conta(c)
        uid = next(a["id"] for a in (await c.get("/v1/transfers")).json())
        r = await c.post("/v1/transfers/unmark", json={"uid": uid})
        assert r.status_code == 200
        resumo = (await c.get("/v1/transactions/summary")).json()
        assert resumo["total_expenses"] + resumo["total_income"] > 0
        # reenviar os arquivos não refaz a marcação que o usuário desfez
        await _importar_par_com_conta(c)
        depois = (await c.get("/v1/transactions/summary")).json()
        assert depois["total_expenses"] + depois["total_income"] > 0
        assert (await c.post("/v1/transfers/unmark", json={"uid": "nada"})).status_code == 404


@pytest.mark.asyncio
async def test_desfazer_a_transferencia_automatica_desmarca_as_duas_pontas():
    async with cliente() as c:
        await _importar_par_com_conta(c)
        uid = (await c.get("/v1/transfers")).json()[0]["id"]
        await c.post("/v1/transfers/unmark", json={"uid": uid})
        resumo = (await c.get("/v1/transactions/summary")).json()
        assert (await c.get("/v1/transfers")).json() == []
    assert resumo["excluded_count"] == 0
    assert resumo["total_expenses"] == 308.76 and resumo["total_income"] == 308.76


@pytest.mark.asyncio
async def test_documento_banco_e_agencia_da_contraparte_nunca_aparecem_na_api():
    async with cliente() as c:
        await _importar_par_com_conta(c)
        texto = (await c.get("/v1/transactions")).text + (await c.get("/v1/transfers")).text
    for proibido in ["11.111.111", "123.456", "Agência", "(0260)", "counterparty_account"]:
        assert proibido not in texto
