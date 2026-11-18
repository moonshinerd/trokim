from datetime import date

import pytest

from app.domain.models import Transaction, TransactionType
from app.services.installment_service import InstallmentService
from tests.helpers_api import cliente, enviar
from tests.nubank_samples import CARTAO_PJ, fatura_cartao, lancamento

D = lancamento


def _tx(merchant, amount, n, total, day, account="c1", tipo=TransactionType.DEBIT, dup=False):
    return Transaction(
        account_id=account,
        description=merchant,
        merchant=merchant,
        amount=amount,
        date=day,
        type=tipo,
        installment_number=n,
        installment_total=total,
        is_duplicate=dup,
    )


def test_mesma_compra_vista_em_faturas_diferentes_vira_um_parcelamento():
    dados = InstallmentService.build(
        [
            _tx("Loja Y", 89.90, 3, 10, date(2026, 10, 5)),
            _tx("Loja Y", 89.90, 4, 10, date(2026, 11, 5)),
        ]
    )
    (plano,) = dados["plans"]
    assert plano["current"] == 4 and plano["paid"] == 2 and plano["remaining"] == 6
    assert plano["remaining_amount"] == pytest.approx(539.40)
    assert plano["ends_on_month"] == "2027-05"
    meses = [m["month"] for m in dados["monthly_projection"]]
    assert meses == ["2026-12", "2027-01", "2027-02", "2027-03", "2027-04", "2027-05"]
    assert all(m["total"] == 89.90 for m in dados["monthly_projection"])
    assert dados["total_remaining"] == pytest.approx(539.40)
    assert dados["active_count"] == 1 and dados["finished_count"] == 0


def test_parcelamento_quitado_nao_entra_na_projecao():
    dados = InstallmentService.build([_tx("Loja", 97.58, 2, 2, date(2026, 11, 10))])
    assert dados["plans"][0]["finished"] is True
    assert dados["active_count"] == 0
    assert dados["total_remaining"] == 0
    assert dados["monthly_projection"] == []


def test_virada_de_ano_na_projecao():
    dados = InstallmentService.build([_tx("Loja", 10.0, 9, 12, date(2026, 11, 20))])
    assert [m["month"] for m in dados["monthly_projection"]] == ["2026-12", "2027-01", "2027-02"]
    assert dados["plans"][0]["ends_on_month"] == "2027-02"


def test_compras_diferentes_na_mesma_loja_nao_se_misturam():
    dados = InstallmentService.build(
        [
            _tx("Loja", 100.0, 1, 5, date(2026, 11, 1)),
            _tx("Loja", 250.0, 1, 5, date(2026, 11, 2)),
            _tx("Loja", 100.0, 1, 3, date(2026, 11, 3)),  # outro total de parcelas
        ]
    )
    assert len(dados["plans"]) == 3


def test_diferenca_de_centavos_entre_parcelas_e_a_mesma_compra():
    dados = InstallmentService.build(
        [
            _tx("Loja", 33.33, 1, 3, date(2026, 9, 1)),
            _tx("Loja", 33.34, 2, 3, date(2026, 10, 1)),
        ]
    )
    assert len(dados["plans"]) == 1
    assert dados["plans"][0]["paid"] == 2


def test_arquivo_reenviado_nao_conta_a_parcela_duas_vezes():
    dados = InstallmentService.build(
        [
            _tx("Loja", 50.0, 2, 4, date(2026, 11, 1)),
            _tx("Loja", 50.0, 2, 4, date(2026, 11, 1), dup=True),
            _tx("Loja", 50.0, 2, 4, date(2026, 11, 1)),
        ]
    )
    assert dados["plans"][0]["paid"] == 1
    assert dados["plans"][0]["remaining"] == 2


def test_dados_invalidos_e_estornos_sao_ignorados():
    dados = InstallmentService.build(
        [
            _tx("Loja", 50.0, 5, 4, date(2026, 11, 1)),  # parcela maior que o total
            _tx("Loja", 50.0, 0, 4, date(2026, 11, 1)),  # parcela zero
            _tx("Loja", 50.0, 1, 4, date(2026, 11, 1), tipo=TransactionType.CREDIT),
            Transaction(
                account_id="c1",
                description="Sem parcela",
                amount=10,
                date=date(2026, 11, 1),
                type=TransactionType.DEBIT,
            ),
        ]
    )
    assert dados["plans"] == []


def test_mesma_compra_em_cartoes_diferentes_sao_planos_diferentes():
    dados = InstallmentService.build(
        [
            _tx("Loja", 50.0, 1, 4, date(2026, 11, 1), account="cartao_pf"),
            _tx("Loja", 50.0, 1, 4, date(2026, 11, 1), account="cartao_pj"),
        ]
    )
    assert len(dados["plans"]) == 2


@pytest.mark.asyncio
async def test_endpoint_agrupa_parcelas_de_duas_faturas_do_cartao_identificado():
    out = fatura_cartao(
        [D("DEBIT", "20261005", "-99.80", "o1", "Mercado Livre - Parcela 4/6")],
        inicio="20261003",
        fim="20261103",
        gerado="20261118",
    )
    nov = fatura_cartao(
        [
            D("DEBIT", "20261105", "-99.80", "n1", "Mercado Livre - Parcela 5/6"),
            D("DEBIT", "20261106", "-55.00", "n2", "Loja Teste - Parcela 6/9"),
            D("DEBIT", "20261107", "-10.00", "n3", "Padaria"),
        ],
        inicio="20261104",
        fim="20261203",
        gerado="20261118",
    )
    async with cliente() as c:
        await enviar(c, out, "out.ofx", owner="pessoal")
        await enviar(c, nov, "nov.ofx", owner="pessoal")
        dados = (await c.get("/v1/installments")).json()
    assert dados["active_count"] == 2
    ml = next(p for p in dados["plans"] if p["merchant"] == "Mercado Livre")
    assert ml["current"] == 5 and ml["paid"] == 2 and ml["remaining"] == 1
    assert dados["total_remaining"] == pytest.approx(99.80 + 3 * 55.00)
    assert ml["account_label"] == "Nubank · cartão"


@pytest.mark.asyncio
async def test_endpoint_com_cartao_da_empresa_mostra_o_rotulo_certo():
    arquivo = fatura_cartao(
        [D("DEBIT", "20261105", "-50.00", "x1", "Loja - Parcela 1/3")],
        acct=CARTAO_PJ,
        gerado="20261118",
        fim="20261203",
    )
    async with cliente() as c:
        await enviar(c, arquivo, owner="empresa")
        dados = (await c.get("/v1/installments")).json()
    assert dados["plans"][0]["account_label"] == "Nubank Empresas · cartão"


@pytest.mark.asyncio
async def test_sem_parcelamentos_a_resposta_vem_zerada():
    async with cliente() as c:
        dados = (await c.get("/v1/installments")).json()
    assert dados == {
        "plans": [],
        "active_count": 0,
        "finished_count": 0,
        "total_remaining": 0,
        "monthly_projection": [],
    }
