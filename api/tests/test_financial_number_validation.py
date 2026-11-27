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
