from datetime import date

import pytest

from app.domain.models import TransactionCategory, TransactionNature, TransactionType
from app.services.calculation_service import CalculationService
from app.services.pdf_profiles import is_bb_fatura, parse_bb_fatura, parse_pdf_statement
from tests.bb_samples import FATURA_PADRAO, PAGAMENTO, fatura_bb, pdf_de_linhas
from tests.helpers_api import cliente
from tests.nubank_samples import CONTA_PF, extrato_conta, lancamento

N = TransactionNature


def _parse(pdf: bytes = FATURA_PADRAO):
    resultado = parse_pdf_statement(pdf, "fatura.pdf")
    assert resultado is not None
    return resultado


def test_banco_cartao_final_e_periodo_da_fatura():
    r = _parse()
    assert (r.institution, r.kind) == ("bb", "cartao")
    assert r.meta.acct_id == "ourocard-1234"
    assert r.meta.period_end == date(2026, 10, 28)
    assert r.meta.period_start == date(2026, 9, 29)
    assert r.ledger_balance == -300.00


def test_valor_positivo_e_compra_e_negativo_e_o_pagamento_da_fatura():
    r = _parse()
    pagamento = next(t for t in r.transactions if t.nature == N.CARD_PAYMENT)
    assert pagamento.type == TransactionType.CREDIT and pagamento.amount == 1000.00
    compras = [t for t in r.transactions if t.nature == N.PURCHASE]
    assert len(compras) == 5 and all(t.type == TransactionType.DEBIT for t in compras)
    assert sum(t.amount for t in compras) == pytest.approx(300.00)


def test_o_total_do_arquivo_fecha_com_os_lancamentos():
    assert _parse().reconciled is True
    errado = fatura_bb(
        [PAGAMENTO, ("Lazer", ["16/10     CINE EXEMPLO     BRASILIA BR R$ 40,00"])], total="999,00"
    )
    assert parse_pdf_statement(errado, "f.pdf").reconciled is False


def test_cidade_nao_entra_no_nome_e_prefixos_sao_removidos():
    nomes = {t.merchant for t in _parse().transactions if t.merchant}
    assert "PIZZARIA EXEMPLO - SAO PAULO" in nomes  # separador de um espaço: parte do nome
    assert "RESTAURANTE EXEMPLO" in nomes
    assert "CINE EXEMPLO" in nomes


def test_parcela_e_extraida_e_sai_da_descricao():
    loja = next(t for t in _parse().transactions if t.installment_total)
    assert (loja.installment_number, loja.installment_total) == (3, 10)
    assert loja.merchant == "LOJA EXEMPLO"


def test_categoria_do_proprio_banco_serve_de_dica():
    r = _parse()
    por_nome = {t.merchant: t.category for t in r.transactions if t.merchant}
    assert por_nome["RESTAURANTE EXEMPLO"] == TransactionCategory.FOOD
    assert por_nome["CINE EXEMPLO"] == TransactionCategory.LEISURE
    assert por_nome["SERVICO EXEMPLO"] == TransactionCategory.SERVICES
    assert por_nome["LOJA EXEMPLO"] == TransactionCategory.OTHER  # BB: "Compras parceladas"


def test_totais_ignoram_o_pagamento_e_somam_so_as_compras():
    resumo = CalculationService.calculate_summary(_parse().transactions)
    assert resumo.total_expenses == pytest.approx(300.00)
    assert resumo.total_income == 0
    assert resumo.excluded_count == 1


def test_ano_da_data_acompanha_o_fechamento_na_virada():
    pdf = fatura_bb(
        [
            (
                "Lazer",
                [
                    "20/12     CINE EXEMPLO     BRASILIA BR R$ 10,00",
                    "05/01     CINE EXEMPLO     BRASILIA BR R$ 10,00",
                ],
            )
        ],
        fechamento="28/01/2027",
        anterior="0,00",
        total="20,00",
    )
    datas = sorted(t.date for t in _parse(pdf).transactions)
    assert datas == [date(2026, 12, 20), date(2027, 1, 5)]


def test_estorno_vira_estorno_e_nao_pagamento_de_fatura():
    pdf = fatura_bb(
        [
            (
                "Lazer",
                [
                    "14/10     CINE EXEMPLO     BRASILIA BR R$ 40,00",
                    "16/10     ESTORNO CINE EXEMPLO     BRASILIA BR R$ -40,00",
                ],
            )
        ],
        anterior="0,00",
        total="0,00",
    )
    naturezas = {t.nature for t in _parse(pdf).transactions}
    assert N.REFUND in naturezas and N.CARD_PAYMENT not in naturezas
    resumo = CalculationService.calculate_summary(_parse(pdf).transactions)
    assert resumo.total_expenses == 0 and resumo.total_income == 0


def test_tarifa_e_anuidade_viram_tarifa():
    pdf = fatura_bb(
        [("Serviços", ["14/10     ANUIDADE DIFERENCIADA     BRASILIA BR R$ 25,00"])],
        anterior="0,00",
        total="25,00",
    )
    assert _parse(pdf).transactions[0].nature == N.FEE


def test_compra_em_moeda_estrangeira_le_o_valor_em_reais():
    pdf = fatura_bb(
        [("Lazer", ["14/10     SERVICO EXTERIOR     LONDON US USD 10,00 R$ 55,00"])],
        anterior="0,00",
        total="55,00",
    )
    (tx,) = _parse(pdf).transactions
    assert tx.amount == 55.00


def test_linhas_iguais_na_mesma_fatura_nao_sao_duplicatas():
    pdf = fatura_bb(
        [
            (
                "Restaurantes",
                [
                    "14/10     CAFE EXEMPLO     BRASILIA BR R$ 8,00",
                    "14/10     CAFE EXEMPLO     BRASILIA BR R$ 8,00",
                ],
            )
        ],
        anterior="0,00",
        total="16,00",
    )
    from app.services.parser_service import ParserService

    txs = _parse(pdf).transactions
    ParserService.deduplicate(txs)
    assert not any(t.is_duplicate for t in txs)


def test_pdf_que_nao_e_do_bb_continua_no_parser_generico():
    outro = pdf_de_linhas(["EXTRATO QUALQUER", "05/11 LOJA -R$ 10,00"])
    assert parse_pdf_statement(outro, "x.pdf") is None
    assert not is_bb_fatura("Fatura qualquer de outro banco")


def test_fatura_sem_fechamento_ou_sem_final_do_cartao_nao_e_lida():
    assert parse_bb_fatura("www.bb.com.br Fatura fechada em 28/10/2026", "f.pdf") is None
    assert parse_bb_fatura("www.bb.com.br OUROCARD VISA Final 1234", "f.pdf") is None


@pytest.mark.asyncio
async def test_upload_do_pdf_do_bb_cadastra_cartao_periodo_e_situacao():
    async with cliente() as c:
        r = await c.post(
            "/v1/transactions/upload",
            files={"file": ("fatura.pdf", FATURA_PADRAO)},
            data={"owner": "pessoal"},
        )
        corpo = r.json()
        assert r.status_code == 200
        assert corpo["institution"] == "bb" and corpo["kind"] == "cartao"
        assert corpo["reconciled"] is True
        assert corpo["account"]["display_label"] == "Banco do Brasil · cartão final 1234"
        assert corpo["statement"]["status"] == "fechada"
        assert corpo["summary"]["total_expenses"] == 300.0
        # reenviar não conta duas vezes
        again = (
            await c.post(
                "/v1/transactions/upload",
                files={"file": ("fatura.pdf", FATURA_PADRAO)},
                data={"owner": "pessoal"},
            )
        ).json()
        assert again["outcome"] == "repetido"
        assert again["summary"]["total_expenses"] == 300.0
        parcelas = (await c.get("/v1/installments")).json()
    assert parcelas["plans"][0]["current"] == 3 and parcelas["plans"][0]["remaining"] == 7
    assert parcelas["plans"][0]["account_label"] == "Banco do Brasil · cartão final 1234"


@pytest.mark.asyncio
async def test_inspecionar_pdf_do_bb_mostra_banco_tipo_e_periodo():
    async with cliente() as c:
        r = await c.post("/v1/transactions/inspect", files={"file": ("fatura.pdf", FATURA_PADRAO)})
        corpo = r.json()
        assert corpo["institution"] == "bb" and corpo["kind"] == "cartao"
        assert corpo["period"]["status"] == "fechada"
        assert corpo["period"]["end"] == "2026-10-28"
        erro = await c.post(
            "/v1/transactions/inspect",
            files={"file": ("fatura.pdf", FATURA_PADRAO)},
            data={"expect_kind": "conta"},
        )
        assert erro.json()["has_conflict"] is True


@pytest.mark.asyncio
async def test_pdf_ilegivel_devolve_erro_e_pdf_sem_perfil_nao_tem_o_que_detectar():
    outro = pdf_de_linhas(["EXTRATO QUALQUER", "05/11 LOJA -R$ 10,00"])
    async with cliente() as c:
        quebrado = await c.post("/v1/transactions/inspect", files={"file": ("x.pdf", b"%PDF")})
        assert quebrado.status_code == 400
        generico = (
            await c.post("/v1/transactions/inspect", files={"file": ("x.pdf", outro)})
        ).json()
    assert generico["institution"] is None and generico["warnings"] == []


# --- pagamento da fatura entre bancos ------------------------------------------------------

PIX_PARA_BB = (
    "Transferência enviada pelo Pix - BANCO DO BRASIL S.A. - 00.000.000/0001-91 - "
    "BANCO DO BRASIL S.A. (0001) Agência: 1 Conta: 9-9"
)


async def _enviar_bb_e_conta(c, valor_pix="1000.00", dia="20261013"):
    await c.post(
        "/v1/transactions/upload",
        files={"file": ("fatura.pdf", FATURA_PADRAO)},
        data={"owner": "pessoal"},
    )
    conta = extrato_conta(
        [lancamento("DEBIT", dia, f"-{valor_pix}", "p1", PIX_PARA_BB)],
        acct=CONTA_PF,
        gerado="20261201",
    )
    await c.post(
        "/v1/transactions/upload",
        files={"file": ("NU_000000000_01OUT2026_31OUT2026.ofx", conta)},
        data={"owner": "pessoal"},
    )


@pytest.mark.asyncio
async def test_pix_que_paga_a_fatura_de_outro_banco_e_sugerido_como_pagamento():
    async with cliente() as c:
        await _enviar_bb_e_conta(c)
        sugestoes = (await c.get("/v1/transfers/suggestions")).json()
    assert len(sugestoes) == 1
    s = sugestoes[0]
    assert s["kind"] == "pagamento_fatura" and s["confidence"] == "alta"
    assert s["to_label"] == "Banco do Brasil · cartão final 1234"


@pytest.mark.asyncio
async def test_confirmar_o_pagamento_evita_contar_a_mesma_conta_duas_vezes():
    async with cliente() as c:
        await _enviar_bb_e_conta(c)
        antes = (await c.get("/v1/transactions/summary?view=competencia")).json()
        assert antes["total_expenses"] == 1300.0  # 300 de compras + 1000 do Pix, em dobro
        s = (await c.get("/v1/transfers/suggestions")).json()[0]
        r = await c.post(
            "/v1/transfers/confirm",
            json={"debit_uid": s["debit_uid"], "credit_uid": s["credit_uid"]},
        )
        assert r.status_code == 200
        comp = (await c.get("/v1/transactions/summary?view=competencia")).json()
        caixa = (await c.get("/v1/transactions/summary?view=caixa")).json()
        confirmadas = (await c.get("/v1/transfers")).json()
    assert comp["total_expenses"] == 300.0  # só as compras do cartão
    assert caixa["total_expenses"] == 1000.0  # só o que saiu da conta
    assert confirmadas[0]["transfer_kind"] == "pagamento_fatura"


@pytest.mark.asyncio
async def test_desfazer_o_pagamento_devolve_a_despesa_da_conta():
    async with cliente() as c:
        await _enviar_bb_e_conta(c)
        s = (await c.get("/v1/transfers/suggestions")).json()[0]
        pid = (
            await c.post(
                "/v1/transfers/confirm",
                json={"debit_uid": s["debit_uid"], "credit_uid": s["credit_uid"]},
            )
        ).json()["id"]
        await c.post("/v1/transfers/undo", json={"id": pid})
        resumo = (await c.get("/v1/transactions/summary")).json()
    assert resumo["total_expenses"] == 1300.0


@pytest.mark.asyncio
async def test_pagamento_com_valor_diferente_ou_fora_da_janela_nao_e_sugerido():
    async with cliente() as c:
        await _enviar_bb_e_conta(c, valor_pix="999.99")
        assert (await c.get("/v1/transfers/suggestions")).json() == []
    async with cliente() as c:
        await c.delete("/v1/transactions/clear")
        await _enviar_bb_e_conta(c, dia="20261020")  # 7 dias depois
        assert (await c.get("/v1/transfers/suggestions")).json() == []
