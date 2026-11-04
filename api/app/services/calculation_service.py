from collections.abc import Sequence

from app.domain.models import (
    BudgetScenario,
    FinancialSummary,
    Transaction,
    TransactionType,
)


class CalculationService:
    """Serviço puramente determinístico para cálculos financeiros.

    Regra de ouro (ADR 0004): A LLM nunca realiza cálculos aritméticos diretamente;
    todos os totais, somas, despesas e projeções são computados com precisão por este serviço.
    """

    @staticmethod
    def calculate_summary(transactions: Sequence[Transaction]) -> FinancialSummary:
        total_income = 0.0
        total_expenses = 0.0
        by_category: dict[str, float] = {}

        for tx in transactions:
            if tx.is_duplicate:
                continue

            category_name = tx.category.value if hasattr(tx.category, "value") else str(tx.category)

            if tx.type == TransactionType.CREDIT:
                total_income += tx.amount
            elif tx.type == TransactionType.DEBIT:
                total_expenses += tx.amount
                by_category[category_name] = by_category.get(category_name, 0.0) + tx.amount

        total_income = round(total_income, 2)
        total_expenses = round(total_expenses, 2)
        net_balance = round(total_income - total_expenses, 2)

        savings_rate = 0.0
        if total_income > 0:
            savings_rate = round((net_balance / total_income) * 100.0, 2)

        rounded_categories = {k: round(v, 2) for k, v in by_category.items()}

        return FinancialSummary(
            total_income=total_income,
            total_expenses=total_expenses,
            net_balance=net_balance,
            savings_rate=savings_rate,
            expenses_by_category=rounded_categories,
            transaction_count=len(transactions),
        )

    @staticmethod
    def compare_budget_scenarios(
        scenario_a: BudgetScenario,
        scenario_b: BudgetScenario,
    ) -> dict[str, object]:
        """Compara dois cenários orçamentários previstos no MVP."""
        margin_a = round(
            scenario_a.monthly_income
            - (
                scenario_a.fixed_expenses + scenario_a.variable_expenses + scenario_a.target_savings
            ),
            2,
        )
        margin_b = round(
            scenario_b.monthly_income
            - (
                scenario_b.fixed_expenses + scenario_b.variable_expenses + scenario_b.target_savings
            ),
            2,
        )

        delta_savings = round(scenario_b.target_savings - scenario_a.target_savings, 2)
        delta_variable = round(scenario_b.variable_expenses - scenario_a.variable_expenses, 2)

        return {
            "scenario_a": {
                "name": scenario_a.name,
                "projected_margin": margin_a,
                "target_savings": scenario_a.target_savings,
            },
            "scenario_b": {
                "name": scenario_b.name,
                "projected_margin": margin_b,
                "target_savings": scenario_b.target_savings,
            },
            "comparison": {
                "delta_savings": delta_savings,
                "delta_variable_expenses": delta_variable,
                "recommendation": (
                    "Cenário B oferece maior reserva projetada."
                    if delta_savings > 0
                    else "Cenário A preserva maior margem operacional."
                ),
            },
        }
