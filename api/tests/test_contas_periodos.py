import pytest

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


def _fatura_aberta(extra: list[str] | None = None, gerado: str = "20261118") -> bytes:
    return fatura_cartao(
        [
            D("DEBIT", "20261105", "-10.00", "a1", "Loja X"),
            D("DEBIT", "20261114", "-20.00", "a2", "Loja Y"),
            *(extra or []),
        ],
        inicio="20261103",
        fim="20261203",
        gerado=gerado,
    )


@pytest.mark.asyncio
async def test_fatura_aberta_e_identificada_pelo_ciclo():
    async with cliente() as c:
        corpo = (await enviar(c, _fatura_aberta())).json()
    st = corpo["statement"]
    assert st["status"] == "aberta"
    assert st["closes_on"] == "2026-12-03"
    assert st["period_start"] == "2026-11-03"
    assert st["covered_until"] == "2026-11-14"  # último lançamento
    assert st["user_confirmed"] is False
    assert corpo["kind"] == "cartao"


@pytest.mark.asyncio
async def test_fatura_fechada_e_identificada():
    arquivo = fatura_cartao(
        [D("DEBIT", "20261019", "-10.00", "f1", "Loja X")],
        acct=CARTAO_PJ,
        inicio="20261011",
        fim="20261111",
        gerado="20261118",
    )
    async with cliente() as c:
        st = (await enviar(c, arquivo)).json()["statement"]
    assert st["status"] == "fechada"
    assert st["closes_on"] is None
    assert st["covered_until"] == "2026-11-11"


@pytest.mark.asyncio
async def test_extrato_gerado_no_ultimo_dia_do_periodo_e_parcial():
    arquivo = extrato_conta(
        [D("DEBIT", "20261020", "-5.00", "e1", "Compra no débito - LOJA")], gerado="20261031"
    )
    async with cliente() as c:
        st = (await enviar(c, arquivo)).json()["statement"]
    assert st["status"] == "parcial"


@pytest.mark.asyncio
async def test_extrato_gerado_no_meio_do_periodo_cobre_ate_o_ultimo_lancamento():
    arquivo = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], gerado="20261015"
    )
    async with cliente() as c:
        st = (await enviar(c, arquivo)).json()["statement"]
    assert st["status"] == "parcial"
    assert st["covered_until"] == "2026-10-12"


@pytest.mark.asyncio
async def test_extrato_de_mes_passado_e_fechado():
    arquivo = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "e1", "Compra no débito - LOJA")], gerado="20261105"
    )
    async with cliente() as c:
        assert (await enviar(c, arquivo)).json()["statement"]["status"] == "fechada"


@pytest.mark.asyncio
async def test_arquivo_sem_data_de_geracao_tem_situacao_desconhecida():
    arquivo = fatura_cartao([D("DEBIT", "20261105", "-10.00", "a1", "Loja X")], gerado=None)
    async with cliente() as c:
        st = (await enviar(c, arquivo)).json()["statement"]
    assert st["status"] == "desconhecida"


@pytest.mark.asyncio
async def test_arquivo_sem_lancamentos_nao_quebra():
    async with cliente() as c:
        corpo = (await enviar(c, fatura_cartao([], gerado="20261118", fim="20261203"))).json()
    assert corpo["imported_count"] == 0
    assert corpo["statement"]["status"] == "aberta"


@pytest.mark.asyncio
async def test_usuario_confirma_e_desfaz_a_situacao():
    async with cliente() as c:
        sid = (await enviar(c, _fatura_aberta())).json()["statement"]["id"]
        r = await c.patch(f"/v1/statements/{sid}", json={"closed": True})
        assert r.json()["status"] == "fechada"
        assert r.json()["user_confirmed"] is True
        assert r.json()["closes_on"] is None
        assert r.json()["covered_until"] == "2026-12-03"
        r = await c.patch(f"/v1/statements/{sid}", json={"closed": False})
        assert r.json()["status"] == "aberta"
        assert r.json()["closes_on"] == "2026-12-03"


@pytest.mark.asyncio
async def test_usuario_configura_o_periodo():
    async with cliente() as c:
        sid = (await enviar(c, _fatura_aberta())).json()["statement"]["id"]
        r = await c.patch(
            f"/v1/statements/{sid}",
            json={"period_start": "2026-11-01", "period_end": "2026-11-30"},
        )
        assert r.status_code == 200
        assert r.json()["period_start"] == "2026-11-01"
        invalido = await c.patch(
            f"/v1/statements/{sid}",
            json={"period_start": "2026-12-10", "period_end": "2026-11-30"},
        )
        assert invalido.status_code == 400
        assert (
            await c.patch("/v1/statements/inexistente", json={"closed": True})
        ).status_code == 404


@pytest.mark.asyncio
async def test_arquivo_diferente_do_mesmo_periodo_atualiza_sem_duplicar():
    async with cliente() as c:
        primeiro = (await enviar(c, _fatura_aberta())).json()
        assert primeiro["outcome"] == "novo"
        segundo = (
            await enviar(
                c,
                _fatura_aberta(
                    [D("DEBIT", "20261116", "-30.00", "a3", "Loja Z")], gerado="20261120"
                ),
            )
        ).json()
        assert segundo["outcome"] == "atualizado"
        assert segundo["delta"] == 1
        assert segundo["summary"]["total_expenses"] == 60.0
        lista = (await c.get("/v1/transactions")).json()
        assert len(lista) == 3
        assert not any(t["is_duplicate"] for t in lista)
        assert len((await c.get("/v1/statements")).json()["statements"]) == 1


@pytest.mark.asyncio
async def test_arquivo_identico_e_repetido_e_nao_altera_totais():
    async with cliente() as c:
        a = (await enviar(c, _fatura_aberta())).json()
        b = (await enviar(c, _fatura_aberta())).json()
    assert b["outcome"] == "repetido"
    assert b["duplicate_count"] == b["imported_count"] == 2
    assert b["summary"]["total_expenses"] == a["summary"]["total_expenses"] == 30.0


@pytest.mark.asyncio
async def test_atualizacao_mantem_a_confirmacao_do_usuario_se_o_periodo_for_o_mesmo():
    async with cliente() as c:
        sid = (await enviar(c, _fatura_aberta())).json()["statement"]["id"]
        await c.patch(f"/v1/statements/{sid}", json={"closed": True})
        novo = (
            await enviar(c, _fatura_aberta([D("DEBIT", "20261116", "-1.00", "a9", "Loja W")]))
        ).json()
    assert novo["statement"]["user_confirmed"] is True
    assert novo["statement"]["status"] == "fechada"


@pytest.mark.asyncio
async def test_lacuna_entre_arquivos_da_mesma_conta_e_listada():
    a = fatura_cartao(
        [D("DEBIT", "20261019", "-10.00", "a1", "Loja X")],
        inicio="20261011",
        fim="20261111",
        gerado="20261211",
    )
    b = fatura_cartao(
        [D("DEBIT", "20261210", "-10.00", "b1", "Loja Y")],
        inicio="20261203",
        fim="20270103",
        gerado="20261211",
    )
    async with cliente() as c:
        await enviar(c, a, "a.ofx")
        await enviar(c, b, "b.ofx")
        cobertura = (await c.get("/v1/statements")).json()["coverage"]
    info = next(iter(cobertura.values()))
    assert info["gaps"] == [{"from": "2026-11-12", "to": "2026-12-02"}]
    assert info["has_open"] is True


@pytest.mark.asyncio
async def test_arquivos_seguidos_nao_tem_lacuna():
    a = fatura_cartao([], inicio="20261011", fim="20261111", gerado="20261211")
    b = fatura_cartao([], inicio="20261112", fim="20261203", gerado="20261211")
    async with cliente() as c:
        await enviar(c, a, "a.ofx")
        await enviar(c, b, "b.ofx")
        info = next(iter((await c.get("/v1/statements")).json()["coverage"].values()))
    assert info["gaps"] == []


@pytest.mark.asyncio
async def test_periodos_sobrepostos_nao_contam_o_mesmo_lancamento_duas_vezes():
    a = extrato_conta(
        [D("DEBIT", "20261012", "-5.00", "x1", "Compra no débito - LOJA")],
        inicio="20261001",
        fim="20261015",
        gerado="20261201",
    )
    b = extrato_conta(
        [
            D("DEBIT", "20261012", "-5.00", "x1", "Compra no débito - LOJA"),
            D("DEBIT", "20261020", "-7.00", "x2", "Compra no débito - OUTRA"),
        ],
        inicio="20261010",
        fim="20261031",
        gerado="20261201",
    )
    async with cliente() as c:
        await enviar(c, a, "a.ofx")
        corpo = (await enviar(c, b, "b.ofx")).json()
    assert corpo["duplicate_count"] == 1
    assert corpo["summary"]["total_expenses"] == 12.0


@pytest.mark.asyncio
async def test_conta_pessoal_e_empresas_do_mesmo_banco_ficam_separadas():
    pf = extrato_conta([D("DEBIT", "20261012", "-100.00", "p1", "Compra no débito - LOJA")])
    pj = extrato_conta(
        [D("DEBIT", "20261013", "-50.00", "j1", "Compra no débito - FORNECEDOR")], acct=CONTA_PJ
    )
    async with cliente() as c:
        await enviar(c, pf, "pf.ofx", owner="pessoal")
        await enviar(c, pj, "pj.ofx", owner="empresa")
        contas = (await c.get("/v1/accounts")).json()
        assert len(contas) == 2
        assert {a["owner"] for a in contas} == {"pessoal", "empresa"}
        assert any(a["display_label"] == "Nubank Empresas · conta" for a in contas)
        todas = (await c.get("/v1/transactions/summary")).json()
        pessoal = (await c.get("/v1/transactions/summary?owner=pessoal")).json()
        empresa = (await c.get("/v1/transactions/summary?owner=empresa")).json()
    assert todas["total_expenses"] == 150.0
    assert pessoal["total_expenses"] == 100.0
    assert empresa["total_expenses"] == 50.0
    assert len(todas["by_account"]) == 2
    assert {r["owner"] for r in todas["by_account"]} == {"pessoal", "empresa"}


@pytest.mark.asyncio
async def test_conta_sem_dono_pede_a_pergunta_e_so_aparece_em_todas():
    arquivo = extrato_conta([D("DEBIT", "20261012", "-9.00", "p1", "Compra no débito - LOJA")])
    async with cliente() as c:
        corpo = (await enviar(c, arquivo)).json()
        assert corpo["account"]["needs_owner"] is True
        assert (await c.get("/v1/transactions/summary?owner=pessoal")).json()["total_expenses"] == 0
        assert (await c.get("/v1/transactions/summary")).json()["total_expenses"] == 9.0
        conta_id = corpo["account"]["id"]
        r = await c.patch(
            f"/v1/accounts/{conta_id}", json={"owner": "pessoal", "label": "Minha conta"}
        )
        assert r.json()["needs_owner"] is False
        assert r.json()["display_label"] == "Minha conta"
        assert (await c.get("/v1/transactions/summary?owner=pessoal")).json()[
            "total_expenses"
        ] == 9.0


@pytest.mark.asyncio
async def test_dono_invalido_e_conta_inexistente():
    arquivo = extrato_conta([])
    async with cliente() as c:
        assert (await enviar(c, arquivo, owner="outro")).status_code == 400
        assert (await c.patch("/v1/accounts/nada", json={"owner": "pessoal"})).status_code == 404
        assert (await c.get("/v1/transactions/summary?owner=xyz")).status_code == 422
        assert (await c.get("/v1/transactions/summary?view=xyz")).status_code == 422


@pytest.mark.asyncio
async def test_competencia_e_caixa_nao_contam_a_mesma_coisa_duas_vezes():
    cartao = fatura_cartao(
        [D("DEBIT", "20261105", "-100.00", "c1", "Loja X")],
        inicio="20261103",
        fim="20261110",
        gerado="20261210",
    )
    conta = extrato_conta(
        [
            D("DEBIT", "20261111", "-80.00", "k1", "Pagamento de fatura"),
            D("DEBIT", "20261112", "-20.00", "k2", "Compra no débito - PADARIA"),
        ],
        inicio="20261101",
        fim="20261130",
        gerado="20261210",
    )
    async with cliente() as c:
        await enviar(c, cartao, "c.ofx", owner="pessoal")
        await enviar(c, conta, "k.ofx", owner="pessoal")
        comp = (await c.get("/v1/transactions/summary?view=competencia")).json()
        caixa = (await c.get("/v1/transactions/summary?view=caixa")).json()
    assert comp["total_expenses"] == 120.0  # compra do cartão + padaria; pagamento fora
    assert caixa["total_expenses"] == 100.0  # pagamento da fatura + padaria; compra do cartão fora
    assert comp["view"] == "competencia" and caixa["view"] == "caixa"


@pytest.mark.asyncio
async def test_uid_e_unico_entre_contas_mesmo_com_o_mesmo_fitid():
    mesmo = [D("DEBIT", "20261012", "-5.00", "igual", "Compra no débito - LOJA")]
    async with cliente() as c:
        await enviar(c, extrato_conta(mesmo), "a.ofx")
        await enviar(c, extrato_conta(mesmo, acct=CONTA_PJ), "b.ofx")
        lista = (await c.get("/v1/transactions")).json()
    assert len({t["uid"] for t in lista}) == 2
    assert not any(t["is_duplicate"] for t in lista)


@pytest.mark.asyncio
async def test_documento_da_contraparte_nunca_sai_pela_api():
    arquivo = extrato_conta(
        [
            D(
                "DEBIT",
                "20261012",
                "-5.00",
                "d1",
                "Transferência enviada pelo Pix - EMPRESA FICTICIA LTDA. - 11.111.111/0001-11 - "
                "BANCO X (0001) Agência: 1 Conta: 1-1",
            )
        ]
    )
    async with cliente() as c:
        await enviar(c, arquivo)
        texto = (await c.get("/v1/transactions")).text
    assert "11.111.111" not in texto and "counterparty_doc" not in texto


@pytest.mark.asyncio
async def test_limpar_zera_arquivos_e_contas():
    async with cliente() as c:
        await enviar(c, _fatura_aberta(), owner="pessoal")
        await c.delete("/v1/transactions/clear")
        assert (await c.get("/v1/accounts")).json() == []
        assert (await c.get("/v1/statements")).json()["statements"] == []
        assert (await c.get("/v1/transactions")).json() == []


def test_cartoes_de_contas_diferentes_tem_ids_diferentes():
    assert CARTAO_PF != CARTAO_PJ and CONTA_PF != CONTA_PJ
