from datetime import date

import pytest

from app.domain.agents import AgentContext, AgentName, StepStatus
from app.domain.models import Transaction, TransactionCategory, TransactionType
from app.services.agents.analysis import AnalysisAgent, extract_goal_and_monthly


@pytest.fixture
def sample_transactions():
    return [
        Transaction(
            account_id="acc1",
            description="Salário Empresa",
            amount=5000.00,
            date=date(2026, 11, 1),
            type=TransactionType.CREDIT,
            category=TransactionCategory.INCOME,
        ),
        Transaction(
            account_id="acc1",
            description="Supermercado ABC",
            amount=1000.00,
            date=date(2026, 11, 2),
            type=TransactionType.DEBIT,
            category=TransactionCategory.FOOD,
        ),
        Transaction(
            account_id="acc1",
            description="Aluguel Apto",
            amount=1500.00,
            date=date(2026, 11, 3),
            type=TransactionType.DEBIT,
            category=TransactionCategory.HOUSING,
        ),
        Transaction(
            account_id="acc1",
            description="Aluguel Duplicado",
            amount=1500.00,
            date=date(2026, 11, 3),
            type=TransactionType.DEBIT,
            category=TransactionCategory.HOUSING,
            is_duplicate=True,  # Não deve entrar nos cálculos
        ),
    ]


def test_extract_goal_and_monthly_formats():
    g1, m1 = extract_goal_and_monthly("Quero juntar R$ 6.000 poupando 500 reais por mês")
    assert g1 == 6000.0
    assert m1 == 500.0

    g2, m2 = extract_goal_and_monthly(
        "Qual o tempo para meta de 12 mil guardando R$ 1.000 mensais?"
    )
    assert g2 == 12000.0
    assert m2 == 1000.0

    g3, m3 = extract_goal_and_monthly("Tenho meta de poupar R$ 5000 com aporte de R$ 600")
    assert g3 == 5000.0
    assert m3 == 600.0


@pytest.mark.asyncio
async def test_analysis_agent_calculates_summary_and_categories(sample_transactions):
    agent = AnalysisAgent()
    ctx = AgentContext(
        question="Qual meu saldo, receitas e despesas por categoria?",
        transactions=sample_transactions,
    )

    step = await agent.run(ctx)

    assert step.agent == AgentName.ANALYSIS
    assert step.status == StepStatus.OK
    assert step.detail["calculations_count"] >= 5

    calc_map = {c.key: c.value for c in ctx.calculations}
    assert calc_map["total_income"] == 5000.0
    assert calc_map["total_expenses"] == 2500.0
    assert calc_map["net_balance"] == 2500.0
    assert calc_map["savings_rate"] == 50.0

    # Categorias
    assert calc_map["expense_alimentacao"] == 1000.0
    assert calc_map["share_alimentacao"] == 40.0  # 1000 / 2500 * 100
    assert calc_map["expense_moradia"] == 1500.0
    assert calc_map["share_moradia"] == 60.0  # 1500 / 2500 * 100

    assert any("sem duplicatas" in a for a in ctx.assumptions)


@pytest.mark.asyncio
async def test_analysis_agent_calculates_goal_without_transactions():
    agent = AnalysisAgent()
    ctx = AgentContext(
        question="Em quantos meses consigo juntar R$ 6.000 poupando R$ 500 por mês?",
        transactions=[],
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.OK
    calc_map = {c.key: c.value for c in ctx.calculations}
    assert calc_map["target_amount"] == 6000.0
    assert calc_map["monthly_savings"] == 500.0
    assert calc_map["months_to_goal"] == 12


@pytest.mark.asyncio
async def test_analysis_agent_skips_when_no_data_available():
    agent = AnalysisAgent()
    ctx = AgentContext(
        question="Qual meu saldo e minhas receitas?",
        transactions=[],
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.SKIPPED
    assert step.detail["reason"] == "sem_calculos"
    assert len(ctx.calculations) == 0
    assert any("Nenhum lançamento foi importado" in a for a in ctx.assumptions)


@pytest.mark.asyncio
async def test_analysis_agent_goal_missing_parameters():
    agent = AnalysisAgent()
    ctx = AgentContext(
        question="Quero planejar minha meta financeira para o fim do ano.",
        transactions=[],
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.SKIPPED
    assert any("informe o valor total e o aporte mensal" in a for a in ctx.assumptions)
