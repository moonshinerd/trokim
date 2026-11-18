import pytest

from app.domain.models import CounterpartyKind, TransactionNature, TransactionType
from app.services.calculation_service import CalculationService
from app.services.parser_service import ParserService
from tests.bb_samples import extrato_bb, lancamento_bb
from tests.helpers_api import cliente, enviar
from tests.nubank_samples import CONTA_PF, extrato_conta, lancamento

N = TransactionNature
B = lancamento_bb
CNPJ_EMPRESA = "59938217000190"
MEMO_TED = f"341 0350 {CNPJ_EMPRESA} EMPRESA EXEMPLO LTDA"
MEMO_PESSOA = "260 0001 12345678909 MARIA EXEMPLO DA SILVA"


def _parse(*lancs: str):
    return ParserService.parse_ofx_detailed(extrato_bb(list(lancs)), "extrato.ofx")


def test_detecta_banco_do_brasil_conta_e_le_o_periodo_do_arquivo():
    r = _parse(
        B("CREDIT", "20261030", "662.33", "202610300662330", "TED-Crédito em Conta", MEMO_TED)
    )
    assert (r.institution, r.kind) == ("bb", "conta")
    assert str(r.meta.period_start) == "2026-08-18" and str(r.meta.period_end) == "2026-10-31"
    assert str(r.meta.generated_at) == "2026-11-18"
    assert r.ledger_balance == 662.94


def test_ted_recebido_traz_contraparte_sem_expor_o_documento():
    (tx,) = _parse(
        B("CREDIT", "20261030", "662.33", "1", "TED-Crédito em Conta", MEMO_TED)
    ).transactions
    assert tx.type == TransactionType.CREDIT and tx.amount == 662.33
    assert tx.nature == N.PIX_IN
    assert tx.merchant == "EMPRESA EXEMPLO LTDA"
    assert tx.counterparty_kind == CounterpartyKind.COMPANY
    assert tx.counterparty_doc == CNPJ_EMPRESA
    assert CNPJ_EMPRESA not in tx.description
    assert "Crédito" not in tx.description or "Ã" not in tx.description


def test_cpf_completo_marca_pessoa_e_nao_aparece_na_descricao():
    (tx,) = _parse(B("DEBIT", "20261030", "-50.00", "2", "Pix - Enviado", MEMO_PESSOA)).transactions
    assert tx.nature == N.PIX_OUT and tx.counterparty_kind == CounterpartyKind.PERSON
    assert "12345678909" not in tx.description and "12345678909" not in (tx.merchant or "")


@pytest.mark.parametrize(
    ("nome", "tipo", "esperado"),
    [
        ("Pix - Recebido", "CREDIT", N.PIX_IN),
        ("Pix - Enviado", "DEBIT", N.PIX_OUT),
        ("TED-Débito em Conta", "DEBIT", N.PIX_OUT),
        ("Pagamento de Fatura Ourocard", "DEBIT", N.CARD_PAYMENT),
        ("Tarifa Pacote de Serviços", "DEBIT", N.FEE),
        ("BB Rende Fácil Aplicação", "DEBIT", N.INVESTMENT_APPLY),
        ("Resgate BB Rende Fácil", "CREDIT", N.INVESTMENT_REDEEM),
        ("IOF", "DEBIT", N.INTEREST),
        ("Compra com Cartão", "DEBIT", N.PURCHASE),
        ("Algo Desconhecido", "DEBIT", N.OTHER),
    ],
)
def test_natureza_pelo_tipo_do_lancamento(nome, tipo, esperado):
    valor = "10.00" if tipo == "CREDIT" else "-10.00"
    (tx,) = _parse(B(tipo, "20261010", valor, "9", nome, "")).transactions
    assert tx.nature == esperado


def test_resgate_e_aplicacao_ficam_fora_dos_totais():
    txs = _parse(
        B("DEBIT", "20261010", "-100.00", "1", "BB Rende Fácil Aplicação"),
        B("CREDIT", "20261011", "100.00", "2", "Resgate BB Rende Fácil"),
        B("DEBIT", "20261012", "-30.00", "3", "Compra com Cartão", "PADARIA EXEMPLO"),
    ).transactions
    resumo = CalculationService.calculate_summary(txs)
    assert resumo.total_expenses == 30.0 and resumo.total_income == 0


def test_acentos_iso_8859_1_nao_corrompem():
    (tx,) = _parse(B("DEBIT", "20261010", "-10.00", "1", "Tarifa Serviços Câmbio")).transactions
    assert "Serviços" in tx.description and "Ã" not in tx.description


@pytest.mark.asyncio
async def test_upload_cadastra_a_conta_do_bb_com_rotulo_e_ficha():
    arquivo = extrato_bb([B("CREDIT", "20261030", "662.33", "1", "TED-Crédito em Conta", MEMO_TED)])
    async with cliente() as c:
        corpo = (await enviar(c, arquivo, "Extrato conta corrente - 102026.ofx", "pessoal")).json()
    assert corpo["institution"] == "bb" and corpo["kind"] == "conta"
    assert corpo["account"]["display_label"] == "Banco do Brasil · conta"
    assert corpo["statement"]["period_start"] == "2026-08-18"
    assert corpo["statement"]["status"] == "fechada"


# --- ligação entre o BB e o Nubank --------------------------------------------------------

PIX_NUBANK_PARA_BB = (
    "Transferência enviada pelo Pix - Maria Exemplo da Silva - •••.345.678-•• - "
    "BANCO DO BRASIL S.A. (0001) Agência: 2895 Conta: 70182-3"
)


async def _par(c, bb_valor="300.00", bb_dia="20261012", bb_extra=None):
    nu = extrato_conta(
        [lancamento("DEBIT", "20261012", "-300.00", "n1", PIX_NUBANK_PARA_BB)], acct=CONTA_PF
    )
    bb = extrato_bb(
        [
            B(
                "CREDIT",
                bb_dia,
                bb_valor,
                "b1",
                "Pix - Recebido",
                "260 0001 12345678909 MARIA EXEMPLO DA SILVA",
            ),
            *(bb_extra or []),
        ]
    )
    await enviar(c, nu, "NU_000000000_01OUT2026_31OUT2026.ofx", "pessoal")
    await enviar(c, bb, "Extrato conta corrente - 102026.ofx", "pessoal")


@pytest.mark.asyncio
async def test_pix_do_nubank_para_a_conta_do_bb_liga_as_duas_pontas():
    async with cliente() as c:
        await _par(c)
        resumo = (await c.get("/v1/transactions/summary")).json()
        itens = (await c.get("/v1/transfers")).json()
    assert resumo["total_expenses"] == 0 and resumo["total_income"] == 0
    assert resumo["excluded_count"] == 2
    assert {i["kind"] for i in itens} == {"automatica"}
    assert len(itens) == 2


@pytest.mark.asyncio
async def test_a_ponta_do_bb_so_e_marcada_se_for_unica():
    async with cliente() as c:
        await _par(
            c,
            bb_extra=[B("CREDIT", "20261012", "300.00", "b2", "Pix - Recebido", MEMO_PESSOA)],
        )
        resumo = (await c.get("/v1/transactions/summary")).json()
    # duas entradas iguais no BB: não dá para saber qual é a ponta; o lado do Nubank já é
    # reconhecido e as entradas ambíguas continuam contando (jamais esconde dinheiro à toa)
    assert resumo["total_income"] == 600.0


@pytest.mark.asyncio
async def test_valor_ou_data_diferentes_nao_ligam_a_ponta_do_bb():
    async with cliente() as c:
        await _par(c, bb_valor="299.99")
        resumo = (await c.get("/v1/transactions/summary")).json()
    assert resumo["total_income"] == 299.99 and resumo["total_expenses"] == 0


@pytest.mark.asyncio
async def test_cnpj_do_nubank_formatado_e_o_mesmo_do_bb_sem_formatacao():
    pix_pj = (
        "Transferência enviada pelo Pix - EMPRESA EXEMPLO LTDA - 59.938.217/0001-90 - "
        "BANCO ITAU (0341) Agência: 1 Conta: 1-1"
    )
    nu = extrato_conta([lancamento("DEBIT", "20261012", "-300.00", "n1", pix_pj)], acct=CONTA_PF)
    bb = extrato_bb([B("CREDIT", "20261012", "300.00", "b1", "TED-Crédito em Conta", MEMO_TED)])
    async with cliente() as c:
        await enviar(c, nu, "nu.ofx", "pessoal")
        await enviar(c, bb, "bb.ofx", "pessoal")
        sug = (await c.get("/v1/transfers/suggestions")).json()
        assert len(sug) == 1
        await c.post(
            "/v1/transfers/confirm",
            json={"debit_uid": sug[0]["debit_uid"], "credit_uid": sug[0]["credit_uid"]},
        )
        # um novo TED do BB para a mesma empresa: o CNPJ aprendido reconhece sem sugestão
        novo = extrato_bb(
            [B("CREDIT", "20261020", "80.00", "b9", "TED-Crédito em Conta", MEMO_TED)],
            inicio="20261101",
            fim="20261130",
        )
        corpo = (await enviar(c, novo, "bb2.ofx", "pessoal")).json()
    assert corpo["auto_transfers"] == 1


@pytest.mark.asyncio
async def test_detector_sabe_que_a_conta_do_bb_e_pessoal_pelos_documentos_do_nubank():
    nu = extrato_conta(
        [lancamento("DEBIT", "20261012", "-300.00", "n1", PIX_NUBANK_PARA_BB)], acct=CONTA_PF
    )
    bb = extrato_bb([B("CREDIT", "20261012", "300.00", "b1", "Pix - Recebido", MEMO_PESSOA)])
    async with cliente() as c:
        await enviar(c, nu, "nu.ofx", "pessoal")
        insp = (
            await c.post(
                "/v1/transactions/inspect",
                files={"file": ("bb.ofx", bb)},
                data={"owner": "empresa"},
            )
        ).json()
    assert insp["has_conflict"] is True and insp["detected_owner"] == "pessoal"


def test_pix_do_bb_traz_data_hora_e_nome_no_memo():
    (tx,) = _parse(
        B("DEBIT", "20260605", "-42.00", "p1", "Pix - Enviado", "05/06 14:23 PADARIA EXEMPLO LTDA")
    ).transactions
    assert tx.nature == N.PIX_OUT
    assert tx.merchant == "PADARIA EXEMPLO LTDA"
    assert tx.counterparty_doc is None
    assert tx.counterparty_kind == CounterpartyKind.COMPANY  # "LTDA" no nome
    assert "14:23" not in tx.description and "14:23" not in (tx.merchant or "")


def test_pix_do_bb_com_documento_identifica_empresa_ou_pessoa():
    (empresa,) = _parse(
        B(
            "DEBIT",
            "20260605",
            "-10.00",
            "p1",
            "Pix - Enviado",
            f"05/06 14:23 {CNPJ_EMPRESA} LOJA EXEMPLO",
        )
    ).transactions
    assert empresa.counterparty_kind == CounterpartyKind.COMPANY
    assert empresa.counterparty_doc == CNPJ_EMPRESA
    (pessoa,) = _parse(
        B(
            "CREDIT",
            "20260606",
            "10.00",
            "p2",
            "Pix - Recebido",
            "06/06 09:00 12345678909 MARIA EXEMPLO",
        )
    ).transactions
    assert pessoa.nature == N.PIX_IN and pessoa.counterparty_kind == CounterpartyKind.PERSON
    assert "12345678909" not in pessoa.description


def test_pagto_cartao_credito_do_bb_e_pagamento_de_fatura():
    (tx,) = _parse(B("DEBIT", "20260610", "-800.00", "c1", "Pagto cartão crédito", "")).transactions
    assert tx.nature == N.CARD_PAYMENT
    assert CalculationService.calculate_summary([tx]).total_expenses == 0


def test_pix_sem_documento_de_nome_sem_marca_de_empresa_e_tratado_como_pessoa():
    (tx,) = _parse(
        B("DEBIT", "20260605", "-30.00", "p1", "Pix - Enviado", "05/06 14:23 JOAO DA SILVA SAURO")
    ).transactions
    assert tx.counterparty_kind == CounterpartyKind.PERSON
    resumo = CalculationService.calculate_summary([tx])
    assert resumo.top_merchants == [{"merchant": "Pix para pessoas", "total": 30.0}]
