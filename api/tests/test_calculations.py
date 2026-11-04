from datetime import date

from app.domain.models import BudgetScenario, Transaction, TransactionCategory, TransactionType
from app.services.calculation_service import CalculationService


def test_calculate_summary_deterministic_precision():
    txs = [
        Transaction(
            account_id="acc1",
            description="Salário",
            amount=5000.00,
            date=date(2026, 11, 1),
            type=TransactionType.CREDIT,
            category=TransactionCategory.INCOME,
        ),
        Transaction(
            account_id="acc1",
            description="Supermercado Central",
            amount=650.50,
            date=date(2026, 11, 2),
            type=TransactionType.DEBIT,
            category=TransactionCategory.FOOD,
        ),
        Transaction(
            account_id="acc1",
            description="Aluguel",
            amount=1500.00,
            date=date(2026, 11, 3),
            type=TransactionType.DEBIT,
            category=TransactionCategory.HOUSING,
        ),
    ]

    summary = CalculationService.calculate_summary(txs)

    assert summary.total_income == 5000.00
    assert summary.total_expenses == 2150.50
    assert summary.net_balance == 2849.50
    assert summary.savings_rate == 56.99
    assert summary.expenses_by_category["alimentacao"] == 650.50
    assert summary.expenses_by_category["moradia"] == 1500.00


def test_calculate_summary_ignores_duplicates():
    txs = [
        Transaction(
            account_id="acc1",
            description="Supermercado Central",
            amount=100.00,
            date=date(2026, 11, 2),
            type=TransactionType.DEBIT,
            category=TransactionCategory.FOOD,
            is_duplicate=False,
        ),
        Transaction(
            account_id="acc1",
            description="Supermercado Central",
            amount=100.00,
            date=date(2026, 11, 2),
            type=TransactionType.DEBIT,
            category=TransactionCategory.FOOD,
            is_duplicate=True,  # Deve ser ignorado
        ),
    ]

    summary = CalculationService.calculate_summary(txs)
    assert summary.total_expenses == 100.00


def test_compare_budget_scenarios():
    scen_a = BudgetScenario(
        name="Cenário Conservador",
        monthly_income=6000.0,
        fixed_expenses=3000.0,
        variable_expenses=1800.0,
        target_savings=800.0,
        projected_margin=0.0,
    )
    scen_b = BudgetScenario(
        name="Cenário Otimizado",
        monthly_income=6000.0,
        fixed_expenses=3000.0,
        variable_expenses=1400.0,
        target_savings=1200.0,
        projected_margin=0.0,
    )

    result = CalculationService.compare_budget_scenarios(scen_a, scen_b)
    comp = result["comparison"]
    assert comp["delta_savings"] == 400.0
    assert comp["delta_variable_expenses"] == -400.0
