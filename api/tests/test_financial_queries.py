"""Consultas determinísticas (#94): cada valor esperado foi conferido à mão, em ``Decimal``.

Cenário (hoje = 20/11/2026), quatro contas, todas sintéticas:

- ``nubank:cc``  conta pessoal      | ``nubank:cp``  cartão pessoal
- ``nubank:cj``  cartão da empresa  | ``bb:conta``   conta da empresa

Contas pessoais em outubro: salário 5.000,00 e aluguel 1.200,50; a transferência própria
(300,00) e o pagamento de fatura (800,00) ficam fora dos totais. Em novembro: mercado 400,25 com
estorno de 50,00 (gasto 350,25) e outra transferência própria (100,00) fora. O lançamento
duplicado de 400,25 não conta.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.models import (
    Account,
    AccountKind,
    AccountOwner,
    Statement,
    StatementStatus,
    Transaction,
    TransactionCategory,
    TransactionNature,
    TransactionType,
)
from app.services.financial_query_service import (
    Clarification,
    FinancialQueryService,
    Period,
    QueryResult,
    Scope,
)
from app.services.library_service import Library

Q = FinancialQueryService
HOJE = date(2026, 11, 20)
CC, CP, CJ, BB = "nubank:cc", "nubank:cp", "nubank:cj", "bb:conta"
DEBIT, CREDIT = TransactionType.DEBIT, TransactionType.CREDIT
N = TransactionNature


def tx(account, day, amount, kind=DEBIT, nature=N.OTHER, merchant=None, category=None, **extra):
    return Transaction(
        id=f"{account}-{day}-{amount}-{merchant}",
        account_id=account,
        description=merchant or "lançamento",
        amount=amount,
        date=date.fromisoformat(day),
        type=kind,
        nature=nature,
        merchant=merchant,
        category=category or TransactionCategory.OTHER,
        **extra,
    )


@pytest.fixture
def library() -> Library:
    lib = Library()
    for account_id, institution, acct, kind, owner in [
        (CC, "nubank", "98765-4", AccountKind.CHECKING, AccountOwner.PERSONAL),
        (CP, "nubank", "11223-3", AccountKind.CARD, AccountOwner.PERSONAL),
        (CJ, "nubank", "55667-8", AccountKind.CARD, AccountOwner.BUSINESS),
        (BB, "bb", "77889-0", AccountKind.CHECKING, AccountOwner.BUSINESS),
    ]:
        lib.accounts[account_id] = Account(
            id=account_id, institution=institution, acct_id=acct, kind=kind, owner=owner
        )
    lib.statements["s1"] = Statement(
        id="s1",
        account_id=CP,
        filename="f1",
        kind=AccountKind.CARD,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        status=StatementStatus.CLOSED,
        due_date=date(2026, 12, 5),
    )
    lib.statements["s2"] = Statement(
        id="s2",
        account_id=CP,
        filename="f2",
        kind=AccountKind.CARD,
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 19),
        status=StatementStatus.OPEN,
        closes_on=date(2026, 11, 30),
    )
    lib.statements["s3"] = Statement(
        id="s3",
        account_id=CJ,
        filename="f3",
        kind=AccountKind.CARD,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        status=StatementStatus.CLOSED,
    )
    c = TransactionCategory
    lib.transactions.extend(
        [
            # Conta pessoal
            tx(CC, "2026-10-05", 5000.00, CREDIT, merchant="Salário", category=c.INCOME),
            tx(CC, "2026-10-10", 1200.50, merchant="Imobiliária X", category=c.HOUSING),
            tx(CC, "2026-10-20", 300.00, nature=N.INTERNAL_TRANSFER),
            tx(CC, "2026-10-25", 800.00, nature=N.CARD_PAYMENT),
            tx(CC, "2026-11-03", 5000.00, CREDIT, merchant="Salário", category=c.INCOME),
            tx(CC, "2026-11-08", 400.25, merchant="Mercado Z", category=c.FOOD),
            tx(CC, "2026-11-08", 400.25, merchant="Mercado Z", category=c.FOOD, is_duplicate=True),
            tx(CC, "2026-11-12", 100.00, nature=N.INTERNAL_TRANSFER),
            tx(
                CC,
                "2026-11-15",
                50.00,
                CREDIT,
                nature=N.REFUND,
                merchant="Mercado Z",
                category=c.FOOD,
            ),
            # Cartão pessoal: fatura fechada (s1) e aberta (s2)
            tx(
                CP,
                "2026-10-09",
                100.00,
                merchant="Loja D",
                category=c.LEISURE,
                source_kind="cartao",
                statement_id="s1",
                installment_number=1,
                installment_total=4,
            ),
            tx(
                CP,
                "2026-10-12",
                200.00,
                merchant="Loja A",
                category=c.LEISURE,
                source_kind="cartao",
                statement_id="s1",
            ),
            tx(
                CP,
                "2026-10-18",
                150.40,
                merchant="Loja B",
                category=c.SERVICES,
                source_kind="cartao",
                statement_id="s1",
            ),
            tx(CP, "2026-11-05", 100.00, CREDIT, nature=N.CARD_PAYMENT, source_kind="cartao"),
            tx(
                CP,
                "2026-11-06",
                90.00,
                merchant="Loja C",
                category=c.LEISURE,
                source_kind="cartao",
                statement_id="s2",
            ),
            tx(
                CP,
                "2026-11-09",
                100.00,
                merchant="Loja D",
                category=c.LEISURE,
                source_kind="cartao",
                statement_id="s2",
                installment_number=2,
                installment_total=4,
            ),
            # Cartão da empresa
            tx(
                CJ,
                "2026-10-14",
                75.10,
                merchant="Fornecedor",
                category=c.SERVICES,
                source_kind="cartao",
                statement_id="s3",
            ),
            # Conta da empresa
            tx(BB, "2026-10-20", 300.00, CREDIT, nature=N.INTERNAL_TRANSFER),
            tx(BB, "2026-11-10", 2000.00, CREDIT, merchant="Cliente", category=c.INCOME),
            tx(BB, "2026-11-14", 650.75, merchant="Contador", category=c.SERVICES),
        ]
    )
    return lib


OUT = Period("mes", "outubro de 2026", date(2026, 10, 1), date(2026, 10, 31))
NOV = Period("mes", "novembro de 2026", date(2026, 11, 1), date(2026, 11, 30))


def ck(account_id: str, kind: str) -> str:
    import hashlib

    return f"account_{hashlib.sha1(account_id.encode()).hexdigest()[:8]}_{kind}"


def val(result: QueryResult, key: str) -> Decimal:
    return Decimal(str(next(c.value for c in result.calculations if c.key == key)))


# ---------------------------------------------------------------- por conta e por dono


def test_por_conta_em_outubro_exclui_transferencia_e_pagamento_de_fatura(library):
    r = Q.by_account(library, OUT)
    # Ordem pelo id: bb, cc, cj, cp.
    assert val(r, ck("bb:conta", "expenses")) == Decimal(
        "0.00"
    )  # a transferência recebida fica fora
    assert val(r, ck("bb:conta", "income")) == Decimal("0.00")
    assert val(r, ck("nubank:cc", "expenses")) == Decimal("1200.50")  # sem 300,00 nem 800,00
    assert val(r, ck("nubank:cc", "income")) == Decimal("5000.00")
    assert val(r, ck("nubank:cc", "balance")) == Decimal("3799.50")
    assert val(r, ck("nubank:cj", "expenses")) == Decimal("75.10")
    assert val(r, ck("nubank:cp", "expenses")) == Decimal("450.40")  # 100 + 200 + 150,40
    assert val(r, ck("nubank:cp", "balance")) == Decimal("-450.40")


def test_por_dono_em_novembro_com_estorno_e_duplicata(library):
    pessoal = Q.by_owner(library, "pessoal", NOV)
    # conta: 400,25 - 50 (estorno) = 350,25; cartão: 90 + 100 = 190; duplicata e transferência fora
    assert val(pessoal, "owner_expenses") == Decimal("540.25")
    assert val(pessoal, "owner_income") == Decimal("5000.00")  # o pagamento de fatura não é receita
    assert val(pessoal, "owner_balance") == Decimal("4459.75")
    empresa = Q.by_owner(library, "empresa", NOV)
    assert val(empresa, "owner_expenses") == Decimal("650.75")
    assert val(empresa, "owner_income") == Decimal("2000.00")
    assert val(empresa, "owner_balance") == Decimal("1349.25")


def test_dono_invalido_pede_esclarecimento(library):
    r = Q.by_owner(library, "ninguem", NOV)
    assert r.clarification and not r.calculations


def test_periodo_sem_lancamento_devolve_zero_e_aviso(library):
    janeiro = Period("mes", "janeiro de 2026", date(2026, 1, 1), date(2026, 1, 31))
    assert val(Q.by_owner(library, "pessoal", janeiro), "owner_expenses") == Decimal("0.00")
    assert Q.by_account(library, janeiro).notes
    assert Q.top_merchants(library, janeiro).notes


def test_visao_de_caixa_conta_o_pagamento_da_fatura(library):
    r = Q.totals(library, Scope((CC,), "todas", "Nubank conta"), OUT, view="caixa")
    assert val(r, "total_expenses") == Decimal("2000.50")  # 1.200,50 + 800,00 (transferência fora)


# ---------------------------------------------------------------- faturas


def test_fatura_aberta_total(library):
    r = Q.statement_total(library, "aberta")
    assert val(r, "statement_aberta") == Decimal("190.00")  # 90 + 100
    assert any("30/11/2026" in note for note in r.notes)


def test_fatura_fechada_com_dois_cartoes_pede_esclarecimento(library):
    r = Q.statement_total(library, "fechada")
    assert r.clarification and not r.calculations
    assert len(r.clarification.options) == 2


def test_fatura_fechada_de_um_cartao(library):
    assert val(Q.statement_total(library, "fechada", Scope((CP,))), "statement_fechada") == Decimal(
        "450.40"
    )
    assert val(Q.statement_total(library, "fechada", Scope((CJ,))), "statement_fechada") == Decimal(
        "75.10"
    )


def test_sem_fatura_aberta_do_cartao_da_empresa(library):
    assert Q.statement_total(library, "aberta", Scope((CJ,))).notes


def test_proxima_fatura_so_com_parcelas_contratadas(library):
    r = Q.next_statement(library, HOJE)
    assert val(r, "next_statement_installments") == Decimal("100.00")  # dezembro: parcela 3/4
    assert any("compras novas" in n for n in r.notes)


def test_proxima_fatura_com_ciclo_fechando_no_inicio_do_mes(library):
    # Ciclo de 03/11 a 03/12: o próximo começa em 04/12 e traz a parcela 3/4 (dezembro).
    library.statements["s2"].closes_on = date(2026, 12, 3)
    r = Q.next_statement(library, HOJE)
    assert val(r, "next_statement_installments") == Decimal("100.00")
    assert "04/12/2026" in r.calculations[0].label


def test_proxima_fatura_com_fechamento_no_dia_25(library):
    # Ciclo aberto fecha em 25/11; o próximo vai de 26/11 a 25/12 e traz a parcela de 09/12.
    library.statements["s2"].closes_on = date(2026, 11, 25)
    r = Q.next_statement(library, HOJE)
    assert val(r, "next_statement_installments") == Decimal("100.00")
    assert "26/11/2026" in r.calculations[0].label and "25/12/2026" in r.calculations[0].label


def test_proxima_fatura_sem_parcela_no_ciclo_e_zero(library):
    library.statements["s2"].closes_on = date(2026, 12, 20)  # próximo ciclo: 21/12 a 20/01
    assert val(Q.next_statement(library, HOJE), "next_statement_installments") == Decimal("100.00")
    library.statements["s2"].closes_on = date(2026, 11, 1)  # ciclo 02/11 a 01/12: sem parcela
    assert val(Q.next_statement(library, HOJE), "next_statement_installments") == Decimal("0.00")


# ---------------------------------------------------------------- parcelas e dívidas


def test_parcelas_em_aberto(library):
    r = Q.open_installments(library)
    assert val(r, "installments_remaining") == Decimal("200.00")  # parcelas 3/4 e 4/4
    assert val(r, "installments_monthly") == Decimal("100.00")
    assert next(c.value for c in r.calculations if c.key == "installments_ends_on") == "2027-01"
    assert val(r, "installments_active") == Decimal("1")


def test_sem_parcelas(library):
    assert Q.open_installments(library, Scope((CC,))).notes


def test_dividas_e_compromissos(library):
    r = Q.commitments(library, HOJE)
    assert val(r, "installments_future") == Decimal("200.00")
    # cartão pessoal: 450,40 - 100,00 pago depois do fechamento = 350,40; empresa: 75,10
    assert val(r, "closed_statement_due") == Decimal("425.50")
    # só a fatura com vencimento informado (05/12, dentro dos 30 dias) entra na janela
    assert val(r, "due_next_30_days") == Decimal("350.40")
    # a da empresa não traz o vencimento: aparece separada, sem chute
    assert val(r, "closed_due_without_date") == Decimal("75.10")
    # parcela de 09/12 cai na janela de 20/11 a 20/12
    assert val(r, "installments_in_window") == Decimal("100.00")
    assert r.notes


def test_vencimento_fora_da_janela_nao_entra(library):
    library.statements["s1"].due_date = date(2027, 1, 20)
    assert val(Q.commitments(library, HOJE), "due_next_30_days") == Decimal("0.00")


def test_janela_de_60_dias_usa_chave_e_rotulo_proprios(library):
    r = Q.commitments(library, HOJE, window_days=60)
    assert val(r, "due_next_60_days") == Decimal("350.40")
    assert "60 dias" in next(c.label for c in r.calculations if c.key == "due_next_60_days")
    assert not any(c.key == "due_next_30_days" for c in r.calculations)


def test_compromissos_respeitam_o_dono(library):
    r = Q.commitments(library, HOJE, Scope(None, "empresa", "empresa"))
    assert val(r, "closed_statement_due") == Decimal("75.10")
    assert val(r, "installments_future") == Decimal("0.00")


def test_fatura_totalmente_paga_nao_e_divida(library):
    library.transactions.append(
        tx(CJ, "2026-11-10", 75.10, CREDIT, nature=N.CARD_PAYMENT, source_kind="cartao")
    )
    assert val(Q.commitments(library, HOJE), "closed_statement_due") == Decimal("350.40")


# ---------------------------------------------------------------- ranking e comparação


def test_top_estabelecimentos_do_mes(library):
    r = Q.top_merchants(library, NOV, limit=3)
    assert [c.label.split(" em ")[0] for c in r.calculations] == ["Contador", "Mercado Z", "Loja D"]
    assert [val(r, f"top_merchant_{i}") for i in (1, 2, 3)] == [
        Decimal("650.75"),
        Decimal("350.25"),  # 400,25 - 50 de estorno
        Decimal("100.00"),
    ]


def test_top_categorias_do_mes(library):
    r = Q.top_categories(library, NOV)
    assert [c.label.split(" em ")[0] for c in r.calculations] == [
        "Categoria servicos",
        "Categoria alimentacao",
        "Categoria lazer",
    ]
    assert [val(r, f"top_category_{i}") for i in (1, 2, 3)] == [
        Decimal("650.75"),
        Decimal("350.25"),
        Decimal("190.00"),  # 90 + 100
    ]


def test_comparacao_entre_periodos(library):
    r = Q.compare_periods(library, OUT, NOV)
    assert val(r, "compare_first") == Decimal("1726.00")  # 1.200,50 + 450,40 + 75,10
    assert val(r, "compare_second") == Decimal("1191.00")  # 540,25 + 650,75
    assert val(r, "compare_delta") == Decimal("-535.00")
    assert val(r, "compare_pct") == Decimal("-31.00")  # -535 / 1726 = -30,9965%


def test_comparacao_sem_base_nao_inventa_percentual(library):
    janeiro = Period("mes", "janeiro de 2026", date(2026, 1, 1), date(2026, 1, 31))
    r = Q.compare_periods(library, janeiro, NOV)
    assert val(r, "compare_first") == Decimal("0.00")
    assert not any(c.key == "compare_pct" for c in r.calculations)
    assert r.notes


def test_efeito_das_transferencias_proprias(library):
    r = Q.own_transfers_effect(library, OUT)
    assert val(r, "own_transfers_out") == Decimal("300.00")
    assert val(r, "card_payments_out") == Decimal("800.00")
    nov = Q.own_transfers_effect(library, NOV)
    assert val(nov, "own_transfers_out") == Decimal("100.00")
    assert val(nov, "card_payments_out") == Decimal("0.00")  # o crédito no cartão não é saída


# ---------------------------------------------------------------- resolução de período


def test_mes_passado_e_este_mes(library):
    assert Q.resolve_period("quanto gastei no mês passado?", library, HOJE) == OUT
    atual = Q.resolve_period("e neste mês?", library, HOJE)
    assert (atual.start, atual.end) == (date(2026, 11, 1), date(2026, 11, 30))


def test_mes_por_nome_usa_o_ano_dos_dados(library):
    p = Q.resolve_period("gastos em outubro", library, HOJE)
    assert (p.start, p.end) == (date(2026, 10, 1), date(2026, 10, 31))
    assert Q.resolve_period("gastos em outubro de 2025", library, HOJE).start == date(2025, 10, 1)


def test_mes_em_mais_de_um_ano_pede_esclarecimento(library):
    library.transactions.append(tx(CC, "2025-10-03", 10.00, merchant="Antigo"))
    r = Q.resolve_period("gastos em outubro", library, HOJE)
    assert isinstance(r, Clarification)
    assert r.options == ("2025", "2026")


def test_mes_sem_dados_usa_o_ultimo_que_ja_passou(library):
    assert Q.resolve_period("em janeiro", library, HOJE).start == date(2026, 1, 1)
    assert Q.resolve_period("em dezembro", library, HOJE).start == date(2025, 12, 1)


def test_intervalo_e_ultimos_dias(library):
    p = Q.resolve_period("de 01/10 a 15/10", library, HOJE)
    assert (p.start, p.end) == (date(2026, 10, 1), date(2026, 10, 15))
    u = Q.resolve_period("nos últimos 7 dias", library, HOJE)
    assert (u.start, u.end) == (date(2026, 11, 14), date(2026, 11, 20))
    assert isinstance(Q.resolve_period("de 15/10 a 01/10", library, HOJE), Clarification)
    assert isinstance(Q.resolve_period("de 31/02 a 01/03", library, HOJE), Clarification)


def test_referencias_de_fatura(library):
    assert Q.resolve_period("quanto está a fatura aberta?", library, HOJE).kind == "fatura_aberta"
    assert Q.resolve_period("a fatura fechada", library, HOJE).kind == "fatura_fechada"
    assert Q.resolve_period("e a próxima fatura?", library, HOJE).kind == "proxima_fatura"


def test_varios_periodos_no_texto_sao_ambiguos_mas_a_comparacao_os_resolve(library):
    texto = "compare outubro e novembro"
    assert isinstance(Q.resolve_period(texto, library, HOJE), Clarification)
    assert [p.label for p in Q.resolve_periods(texto, library, HOJE)] == [
        "outubro de 2026",
        "novembro de 2026",
    ]


def test_sem_periodo_no_texto(library):
    assert Q.resolve_period("quanto eu gasto com mercado?", library, HOJE) is None


# ---------------------------------------------------------------- resolução de conta


def test_fatura_do_nubank_e_ambigua_entre_pessoal_e_empresa(library):
    r = Q.resolve_scope("quanto está a fatura do Nubank?", library)
    assert isinstance(r, Clarification)
    assert r.options == ("Nubank cartão (empresa)", "Nubank cartão (pessoal)")


def test_fatura_do_nubank_da_empresa_e_pessoal(library):
    assert Q.resolve_scope("fatura do Nubank da empresa", library).account_ids == (CJ,)
    assert Q.resolve_scope("fatura do nubank pessoal", library).account_ids == (CP,)


def test_so_dono_e_sem_recorte(library):
    assert Q.resolve_scope("gastos da empresa", library) == Scope(None, "empresa", "empresa")
    assert Q.resolve_scope("quanto gastei?", library) == Scope()


def test_conta_do_banco_do_brasil(library):
    assert Q.resolve_scope("saldo da conta do banco do brasil", library).account_ids == (BB,)


# ---------------------------------------------------------------- privacidade


def test_nada_sensivel_sai_nas_respostas(library):
    library.transactions.append(
        tx(CC, "2026-11-16", 20.00, merchant="Contraparte", counterparty_doc="12345678000199")
    )
    results = [
        Q.by_account(library, NOV),
        Q.by_owner(library, "pessoal", NOV),
        Q.statement_total(library, "aberta"),
        Q.next_statement(library, HOJE),
        Q.open_installments(library),
        Q.commitments(library, HOJE),
        Q.top_merchants(library, NOV),
        Q.top_categories(library, NOV),
        Q.compare_periods(library, OUT, NOV),
        Q.own_transfers_effect(library, OUT),
        Q.statement_total(library, "fechada"),
    ]
    saida = " ".join(
        f"{c.key} {c.label} {c.source}" for r in results for c in r.calculations
    ) + " ".join(n for r in results for n in r.notes)
    saida += " ".join(o for r in results if r.clarification for o in r.clarification.options)
    for segredo in ["98765", "11223", "55667", "77889", "12345678000199", "nubank:cc", "bb:conta"]:
        assert segredo not in saida


def test_contas_com_o_mesmo_rotulo_ganham_numero(library):
    library.accounts["nubank:outra"] = Account(
        id="nubank:outra",
        institution="nubank",
        acct_id="00000-0",
        kind=AccountKind.CARD,
        owner=AccountOwner.PERSONAL,
    )
    r = Q.resolve_scope("fatura do nubank pessoal", library)
    assert isinstance(r, Clarification)
    assert r.options == ("Nubank cartão (pessoal) #1", "Nubank cartão (pessoal) #2")


# ----------------------------------------- extrato sintético de três meses (gabarito multiagente)

LEDGER = Path(__file__).resolve().parents[2] / "research/synthetic_data/ledger_multiagente.json"


@pytest.fixture
def ledger() -> Library:
    lib = Library()
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))["transactions"]
    lib.transactions.extend(Transaction(**row) for row in rows)
    return lib


@pytest.mark.parametrize(
    ("mes", "despesa", "receita", "saldo"),
    [
        # Ago: 1.500 + 620,40 + 410,30 + 220 + 135,90 + 90 + 119,90 + 180 (duplicata fora)
        (8, "3276.50", "5000.00", "1723.50"),
        # Set: 1.500 + 598,70 + 145,50 + 220 + 250 + 210 + 119,90 + 180 (receita 5.000 + 800)
        (9, "3224.10", "5800.00", "2575.90"),
        # Out: 1.500 + 655,10 + 372 + 220 + 88,60 + 55,90 + 119,90 + 180
        (10, "3191.50", "5000.00", "1808.50"),
    ],
)
def test_ledger_de_tres_meses_por_mes(ledger, mes, despesa, receita, saldo):
    period = Q.resolve_period(f"gastos em {MONTH[mes]}", ledger, HOJE)
    r = Q.totals(ledger, Scope(), period)
    assert val(r, "total_expenses") == Decimal(despesa)
    assert val(r, "total_income") == Decimal(receita)
    assert val(r, "net_balance") == Decimal(saldo)


MONTH = {8: "agosto", 9: "setembro", 10: "outubro"}


def test_ledger_comparacao_e_categorias(ledger):
    ago, out = Q.resolve_periods("agosto e outubro", ledger, HOJE)
    r = Q.compare_periods(ledger, ago, out)
    assert val(r, "compare_delta") == Decimal("-85.00")  # 3.191,50 - 3.276,50
    assert val(r, "compare_pct") == Decimal("-2.59")  # -85 / 3276,50
    set_ = Q.resolve_period("em setembro", ledger, HOJE)
    top = Q.top_categories(ledger, set_)
    assert [val(top, f"top_category_{i}") for i in range(1, 6)] == [
        Decimal("1500.00"),  # moradia
        Decimal("744.20"),  # alimentação: 598,70 + 145,50
        Decimal("250.00"),  # saúde
        Decimal("220.00"),  # transporte
        Decimal("210.00"),  # lazer
    ]


# ----------------------------------------------------------- achados da revisão (#94)


def test_recorte_sem_conta_nao_soma_todas(library):
    escopo = Q.resolve_scope("parcelas do Mercado Pago", library)
    assert escopo.account_ids == ()
    for resultado in (
        Q.open_installments(library, escopo),
        Q.commitments(library, HOJE, escopo),
        Q.next_statement(library, HOJE, escopo),
        Q.statement_total(library, "aberta", escopo),
        Q.totals(library, escopo, NOV),
        Q.top_merchants(library, NOV, escopo),
        Q.top_categories(library, NOV, escopo),
        Q.own_transfers_effect(library, NOV, escopo),
        Q.compare_periods(library, OUT, NOV, escopo),
    ):
        assert not resultado.calculations
        assert resultado.notes


@pytest.mark.parametrize("referencia", ["fatura aberta", "fatura fechada", "próxima fatura"])
def test_periodo_de_fatura_nao_vira_total_do_historico(library, referencia):
    periodo = Q.resolve_period(f"top estabelecimentos da {referencia}", library, HOJE)
    assert periodo.start is None
    for resultado in (
        Q.top_merchants(library, periodo),
        Q.top_categories(library, periodo),
        Q.totals(library, None, periodo),
        Q.by_account(library, periodo),
        Q.by_owner(library, "pessoal", periodo),
        Q.own_transfers_effect(library, periodo),
        Q.compare_periods(library, periodo, NOV),
    ):
        assert not resultado.calculations
        assert any("fatura" in nota for nota in resultado.notes)


def test_banco_so_casa_como_palavra_inteira(library):
    library.accounts["inter:1"] = Account(
        id="inter:1", institution="inter", acct_id="1", kind=AccountKind.CHECKING
    )
    assert Q.resolve_scope("gasto com transferência internacional", library) == Scope()
    assert Q.resolve_scope("saldo da conta do inter", library).account_ids == ("inter:1",)


def test_limite_do_ranking_vale_acima_de_cinco(library):
    for i in range(8):
        library.transactions.append(tx(CC, "2026-11-20", 10.00 + i, merchant=f"Loja {i}"))
    assert len(Q.top_merchants(library, NOV, limit=10).calculations) == 10
    assert len(Q.top_merchants(library, NOV, limit=3).calculations) == 3


def test_numero_das_contas_do_mesmo_rotulo_nao_depende_da_ordem_de_insercao(library):
    for ordem in (["nubank:b", "nubank:a"], ["nubank:a", "nubank:b"]):
        lib = Library()
        for aid in ordem:
            lib.accounts[aid] = Account(
                id=aid,
                institution="nubank",
                acct_id=aid,
                kind=AccountKind.CARD,
                owner=AccountOwner.PERSONAL,
            )
        r = Q.resolve_scope("fatura do nubank", lib)
        assert r.options == ("Nubank cartão (pessoal) #1", "Nubank cartão (pessoal) #2")
        from app.services.financial_query_service import _names

        assert _names(lib) == {
            "nubank:a": "Nubank cartão (pessoal) #1",
            "nubank:b": "Nubank cartão (pessoal) #2",
        }


def test_chave_por_conta_nao_muda_com_o_periodo(library):
    janeiro = Period("mes", "janeiro de 2026", date(2026, 1, 1), date(2026, 1, 31))
    library.transactions.append(tx(CP, "2026-01-10", 7.00, merchant="Só no cartão"))
    r = Q.by_account(library, janeiro)
    assert val(r, ck("nubank:cp", "expenses")) == Decimal(
        "7.00"
    )  # a chave é estável: não depende da posição


def test_mes_sem_ano_so_com_dados_de_outro_ano_pergunta(library):
    lib = Library()
    lib.transactions.append(tx(CC, "2025-11-03", 10.00, merchant="Antigo"))
    r = Q.resolve_period("gasto em novembro", lib, HOJE)
    assert isinstance(r, Clarification)
    assert r.options == ("2025", "2026")


def test_statement_due_date_vem_do_pdf_do_itau_e_do_picpay():
    from app.services.bank_pdf_profiles import parse_itau_fatura, parse_picpay_fatura

    itau = parse_itau_fatura(
        "Itaú\nVencimento: 15/12/2026\nlançamentos: compras e saques\n"
        "10/11 LOJA TESTE 25,00\ntotal dos lançamentos atuais 25,00\n",
        "fatura.pdf",
    )
    assert itau is not None and itau.due_date == date(2026, 12, 15)
    picpay = parse_picpay_fatura(
        "PicPay Card final 1234\nVencimento: 20-12-2026\n10/11 LOJA TESTE 30,00\n", "f.pdf"
    )
    assert picpay is not None and picpay.due_date == date(2026, 12, 20)


def test_vencimento_chega_ao_statement_pela_importacao_e_sobrevive_ao_snapshot():
    from app.services.bank_pdf_profiles import parse_itau_fatura
    from app.services.import_service import ImportService

    itau = (
        "itau unibanco\nVencimento: 10/12/2026\nlançamentos: compras e saques\n"
        "03/11 LOJA X 02/05 80,00\n05/11 ESTORNO LOJA -20,00\n"
        "total dos lançamentos atuais 60,00\n"
    )
    lib = Library()
    ImportService.import_parsed(lib, parse_itau_fatura(itau, "fatura.pdf"), "fatura.pdf")
    (statement,) = lib.statements.values()
    assert statement.due_date == date(2026, 12, 10)
    restored = Statement.model_validate_json(statement.model_dump_json())
    assert restored.due_date == date(2026, 12, 10)
    # snapshot antigo, sem o campo: continua válido
    legado = statement.model_dump(mode="json", exclude={"due_date"})
    assert Statement.model_validate(legado).due_date is None


# ----------------------------------------------------------- segundo review (#94)


def _fatura_itau(lib: Library, vencimento: date, pagamento: date | None) -> None:
    """Fatura de R$ 500 em que o fim do período é o vencimento, como nos PDFs Itaú e PicPay."""
    lib.accounts["itau:cartao"] = Account(
        id="itau:cartao", institution="itau", acct_id="1", kind=AccountKind.CARD
    )
    lib.statements["itau"] = Statement(
        id="itau",
        account_id="itau:cartao",
        filename="f.pdf",
        kind=AccountKind.CARD,
        period_start=date(2026, 11, 1),
        period_end=vencimento,
        status=StatementStatus.CLOSED,
        due_date=vencimento,
    )
    lib.transactions.append(
        tx(
            "itau:cartao",
            "2026-11-10",
            500.00,
            merchant="Loja",
            source_kind="cartao",
            statement_id="itau",
        )
    )
    if pagamento:
        lib.transactions.append(
            tx(
                "itau:cartao",
                pagamento.isoformat(),
                500.00,
                CREDIT,
                nature=N.CARD_PAYMENT,
                source_kind="cartao",
            )
        )


def test_pagamento_antes_do_vencimento_abate_a_fatura_do_itau():
    lib = Library()
    _fatura_itau(lib, date(2026, 12, 10), date(2026, 12, 8))
    r = Q.commitments(lib, HOJE)
    assert val(r, "closed_statement_due") == Decimal("0.00")
    assert val(r, "due_next_30_days") == Decimal("0.00")


def test_fatura_vencida_aparece_em_balde_proprio():
    lib = Library()
    _fatura_itau(lib, date(2026, 11, 5), None)
    r = Q.commitments(lib, HOJE)
    assert val(r, "closed_statement_due") == Decimal("500.00")
    assert val(r, "overdue_statement_due") == Decimal("500.00")
    assert val(r, "due_next_30_days") == Decimal("0.00")
    assert val(r, "closed_due_without_date") == Decimal("0.00")
    # os baldes fecham com o total
    baldes = ["overdue_statement_due", "due_next_30_days", "closed_due_without_date"]
    assert sum(val(r, k) for k in baldes) == val(r, "closed_statement_due")


def test_ciclo_fechando_no_ultimo_dia_do_mes_vai_ate_o_ultimo_dia_do_proximo(library):
    library.statements["s2"].closes_on = date(2026, 11, 30)
    library.transactions.append(
        tx(
            CP,
            "2026-11-30",
            40.00,
            merchant="Loja E",
            source_kind="cartao",
            statement_id="s2",
            installment_number=1,
            installment_total=3,
        )
    )  # parcela 2/3 em 30/12 e 3/3 em 30/01
    r = Q.next_statement(library, HOJE)
    assert "01/12/2026 a 31/12/2026" in r.calculations[0].label
    assert val(r, "next_statement_installments") == Decimal("140.00")  # 100 (09/12) + 40 (30/12)


def test_tipo_de_fatura_invalido_nao_cai_em_fechada(library):
    r = Q.statement_total(library, "proxima")
    assert not r.calculations and r.notes


def test_conta_sem_dono_fica_de_fora_com_aviso(library):
    library.accounts["x:sem-dono"] = Account(id="x:sem-dono", institution="x", acct_id="9")
    assert any("sem dono" in n for n in Q.by_owner(library, "pessoal", NOV).notes)
    assert any(
        "sem dono" in n for n in Q.totals(library, Scope(None, "empresa", "empresa"), NOV).notes
    )
    assert not Q.totals(library, Scope(), NOV).notes


def test_conta_de_luz_nao_vira_filtro_de_conta_corrente(library):
    assert Q.resolve_scope("quanto paguei na conta de luz em outubro", library) == Scope()
    assert Q.resolve_scope("saldo da conta corrente do banco do brasil", library).account_ids == (
        BB,
    )


# ----------------------------------------------------------- review final (#94)


def test_pagamento_pela_conta_corrente_quita_a_fatura_do_pdf():
    lib = Library()
    _fatura_itau(lib, date(2026, 11, 5), None)
    lib.accounts["itau:conta"] = Account(
        id="itau:conta", institution="itau", acct_id="2", kind=AccountKind.CHECKING
    )
    lib.transactions.append(tx("itau:conta", "2026-11-04", 500.00, nature=N.CARD_PAYMENT))
    # pagamento anterior ao fechamento das compras da fatura (10/11): não conta
    assert val(Q.commitments(lib, HOJE), "closed_statement_due") == Decimal("500.00")
    lib.transactions.append(tx("itau:conta", "2026-11-12", 500.00, nature=N.CARD_PAYMENT))
    r = Q.commitments(lib, HOJE)
    assert val(r, "closed_statement_due") == Decimal("0.00")
    assert val(r, "overdue_statement_due") == Decimal("0.00")


def test_pagamento_de_valor_diferente_nao_quita(library):
    lib = Library()
    _fatura_itau(lib, date(2026, 11, 5), None)
    lib.accounts["itau:conta"] = Account(
        id="itau:conta", institution="itau", acct_id="2", kind=AccountKind.CHECKING
    )
    lib.transactions.append(tx("itau:conta", "2026-11-12", 499.00, nature=N.CARD_PAYMENT))
    assert val(Q.commitments(lib, HOJE), "closed_statement_due") == Decimal("500.00")


def test_reimportar_o_pdf_grava_o_vencimento_de_fatura_antiga():
    from app.services.bank_pdf_profiles import parse_itau_fatura
    from app.services.import_service import ImportService

    itau = (
        "itau unibanco\nVencimento: 10/12/2026\nlançamentos: compras e saques\n"
        "03/11 LOJA X 80,00\ntotal dos lançamentos atuais 80,00\n"
    )
    lib = Library()
    ImportService.import_parsed(lib, parse_itau_fatura(itau, "f.pdf"), "f.pdf")
    (statement,) = lib.statements.values()
    statement.due_date = None  # importada antes de existir o campo
    resultado = ImportService.import_parsed(lib, parse_itau_fatura(itau, "f.pdf"), "f.pdf")
    assert resultado["outcome"] == "repetido"
    assert statement.due_date == date(2026, 12, 10)


def test_ultimos_zero_dias_pede_esclarecimento(library):
    assert isinstance(Q.resolve_period("gastos dos últimos 0 dias", library, HOJE), Clarification)


def test_conta_com_banco_restringe_a_conta_corrente(library):
    # há conta corrente e cartão do Nubank do mesmo dono: “conta nubank” é a conta corrente
    escopo = Q.resolve_scope("quanto tenho na conta nubank pessoal?", library)
    assert escopo.account_ids == (CC,)


def test_chave_por_conta_nao_vaza_o_id(library):
    r = Q.by_account(library, OUT)
    assert not any("nubank" in c.key or "98765" in c.key for c in r.calculations)
