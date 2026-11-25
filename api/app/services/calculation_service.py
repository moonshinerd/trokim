import math
from collections.abc import Sequence

from app.domain.models import (
    BudgetScenario,
    CounterpartyKind,
    FinancialSummary,
    Transaction,
    TransactionNature,
    TransactionType,
)


class CalculationService:
    """Serviço puramente determinístico para cálculos financeiros.

    Regra de ouro (ADR 0004): A LLM nunca realiza cálculos aritméticos diretamente;
    todos os totais, somas, despesas e projeções são computados com precisão por este serviço.
    """

    @staticmethod
    def months_to_goal(goal: float, monthly_savings: float) -> int:
        """Calcula o número de meses necessários para atingir uma meta de poupança (teto)."""
        if monthly_savings <= 0:
            raise ValueError("O aporte mensal deve ser estritamente maior que zero.")
        if goal <= 0:
            return 0
        return math.ceil(goal / monthly_savings)

    @staticmethod
    def category_shares(summary: FinancialSummary) -> dict[str, float]:
        """Calcula a participação percentual de cada categoria no total de despesas."""
        if summary.total_expenses <= 0:
            return {cat: 0.0 for cat in summary.expenses_by_category}
        return {
            cat: round((amount / summary.total_expenses) * 100.0, 2)
            for cat, amount in summary.expenses_by_category.items()
        }

    @staticmethod
    def _effect(tx: Transaction, view: str) -> str:
        """Como o lançamento entra na visão: ``count``, ``skip`` (outra visão) ou ``exclude``.

        - **Competência** (padrão): compras do cartão contam quando acontecem; o pagamento da
          fatura, resgates, aplicações e transferências próprias ficam de fora.
        - **Caixa**: só o que passou pelas contas. Compras do cartão ficam de fora (a saída é o
          pagamento da fatura, que aqui conta como despesa).
        """
        if tx.is_duplicate:
            return "skip"
        if view == "caixa":
            if tx.source_kind == "cartao":
                return "skip"
            if tx.nature == TransactionNature.CARD_PAYMENT:
                return "count" if tx.type == TransactionType.DEBIT else "exclude"
        return "count" if tx.counts_in_totals else "exclude"

    @staticmethod
    def calculate_summary(
        transactions: Sequence[Transaction],
        view: str = "competencia",
        owner: str = "todas",
        merchant_limit: int = 5,
    ) -> FinancialSummary:
        total_income = 0.0
        total_expenses = 0.0
        by_category: dict[str, float] = {}
        by_merchant: dict[str, float] = {}
        by_account: dict[str, dict[str, float]] = {}
        excluded = 0

        for tx in transactions:
            effect = CalculationService._effect(tx, view)
            if effect == "skip":
                continue
            if effect == "exclude":
                excluded += 1
                continue

            category_name = tx.category.value if hasattr(tx.category, "value") else str(tx.category)
            # Pix para pessoas físicas não entra pelo nome: vira um grupo só.
            merchant_name = (
                "Pix para pessoas"
                if tx.counterparty_kind == CounterpartyKind.PERSON
                else tx.merchant
            )
            account = by_account.setdefault(
                tx.account_id, {"income": 0.0, "expenses": 0.0, "count": 0.0}
            )
            account["count"] += 1

            if tx.type == TransactionType.CREDIT and tx.nature == TransactionNature.REFUND:
                # Estorno abate a despesa; não é renda.
                total_expenses -= tx.amount
                account["expenses"] -= tx.amount
                if tx.category.value != "renda":
                    by_category[category_name] = by_category.get(category_name, 0.0) - tx.amount
                if merchant_name:
                    by_merchant[merchant_name] = by_merchant.get(merchant_name, 0.0) - tx.amount
            elif tx.type == TransactionType.CREDIT:
                total_income += tx.amount
                account["income"] += tx.amount
            elif tx.type == TransactionType.DEBIT:
                total_expenses += tx.amount
                account["expenses"] += tx.amount
                by_category[category_name] = by_category.get(category_name, 0.0) + tx.amount
                if merchant_name:
                    by_merchant[merchant_name] = by_merchant.get(merchant_name, 0.0) + tx.amount

        total_income = round(total_income, 2)
        total_expenses = round(max(total_expenses, 0.0), 2)
        net_balance = round(total_income - total_expenses, 2)

        savings_rate = 0.0
        if total_income > 0:
            savings_rate = round((net_balance / total_income) * 100.0, 2)

        rounded_categories = {k: round(v, 2) for k, v in by_category.items() if v > 0}

        return FinancialSummary(
            total_income=total_income,
            total_expenses=total_expenses,
            net_balance=net_balance,
            savings_rate=savings_rate,
            expenses_by_category=rounded_categories,
            transaction_count=len(transactions),
            excluded_count=excluded,
            view=view,
            owner=owner,
            by_account=[
                {
                    "account_id": account_id,
                    "income": round(values["income"], 2),
                    "expenses": round(max(values["expenses"], 0.0), 2),
                    "count": int(values["count"]),
                }
                for account_id, values in by_account.items()
            ],
            top_merchants=[
                {"merchant": name, "total": round(total, 2)}
                for name, total in sorted(by_merchant.items(), key=lambda kv: -kv[1])[
                    :merchant_limit
                ]
                if total > 0
            ],
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
