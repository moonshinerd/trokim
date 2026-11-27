"""Suporte numérico das consultas pessoais; sem LLM ou rede."""

from datetime import date

import pytest

from app.domain.agents import AgentContext, CalculationResult, FinancialContext
from app.services.agents.validation import ValidationAgent


@pytest.mark.parametrize(
    "draft",
    [
        "Seu saldo é R$ 999,99.",
        "Seu saldo é -100 BRL.",
        "Seu saldo é 100%.",
        "Sua fatura é R$ 2026.",
        "Sua despesa é R$ 30.",
    ],
)
def test_numeros_pessoais_exigem_valor_sinal_e_unidade_do_calculo(draft):
    from app.services.agents.validation import check_financial_numbers

    calculations = [
        CalculationResult(
            key="balance",
            label="Saldo de outubro de 2026",
            value=100,
            unit="BRL",
            source="Sistema",
        )
    ]
    assert check_financial_numbers(draft, calculations, ["Vencimentos nos próximos 30 dias."])


@pytest.mark.parametrize("draft", ["Saldo: R$ 100,00.", "Saldo: 100.0 BRL."])
def test_formato_brasileiro_e_formato_do_calculo_passam(draft):
    from app.services.agents.validation import check_financial_numbers

    assert not check_financial_numbers(
        draft,
        [
            CalculationResult(
                key="balance",
                label="Saldo",
                value=100,
                unit="BRL",
                source="Sistema",
            )
        ],
        [],
    )


async def test_calculo_pessoal_ausente_nao_e_autorizado_pela_pergunta():
    ctx = AgentContext(
        question="Minha fatura é R$ 100?",
        financial=FinancialContext(intent="statement", reference_date=date(2026, 11, 20)),
        draft_answer="Sua fatura é R$ 100.",
    )
    await ValidationAgent().run(ctx)
    assert {i.code for i in ctx.issues} >= {"CALCULATION_MISSING", "NUMBER_NOT_SUPPORTED"}


_SETEMBRO = [
    CalculationResult(
        key="total_expenses",
        label="Gasto (Nubank conta (pessoal)) em setembro de 2026",
        value=561.78,
        unit="BRL",
        source="FinancialQueryService",
    ),
    CalculationResult(
        key="total_income",
        label="Receita (Nubank conta (pessoal)) em setembro de 2026",
        value=7023.92,
        unit="BRL",
        source="FinancialQueryService",
    ),
    CalculationResult(
        key="net_balance",
        label="Saldo (Nubank conta (pessoal)) em setembro de 2026",
        value=6462.14,
        unit="BRL",
        source="FinancialQueryService",
    ),
]


def test_resposta_correta_com_ano_lista_e_conta_passa():
    """Redação real do Mistral Small 3.2 no benchmark da #98: números certos, antes retida."""
    from app.services.agents.validation import check_financial_numbers

    draft = (
        "Os cálculos são da conta pessoal no Nubank em setembro de 2026:\n\n"
        "1. **Gasto total**: 561,78 BRL\n"
        "2. **Receita total**: 7.023,92 BRL\n"
        "3) **Saldo líquido**: 6.462,14 BRL\n\n"
        "O saldo é a receita menos o gasto: 6.462,14 = 7.023,92 - 561,78\n"
        "- 561,78 BRL de gastos no mês."
    )
    assert not check_financial_numbers(draft, _SETEMBRO, [])


@pytest.mark.parametrize(
    "draft",
    [
        "Seu saldo em setembro de 2026 é R$ 2026.",  # ano como dinheiro
        "Em setembro de 2025 você gastou 561,78 BRL.",  # ano que não está nos rótulos
        "1. Gasto total: 999,99 BRL",  # valor inventado numa lista
        "O saldo é 7.023,92 - 999,99.",  # operação com valor inventado
        "Seu saldo é -561,78 BRL.",  # sinal de verdade
        "1 BRL de tarifa.",  # numeral no início da linha com unidade
    ],
)
def test_ano_lista_e_operacao_nao_liberam_numero_inventado(draft):
    from app.services.agents.validation import check_financial_numbers

    assert check_financial_numbers(draft, _SETEMBRO, []), draft
