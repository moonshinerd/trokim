"""Entradas fictícias da comparação; os resultados vêm do serviço financeiro."""

from datetime import date

from app.domain.models import Transaction, TransactionType
from app.services.calculation_service import CalculationService


def calculation_results(fixture: str | None) -> dict:
    if fixture in (None, "sem_resultado"):
        return {}
    if fixture != "resumo_centavos":
        raise ValueError("Massa sintética desconhecida.")
    transactions = [
        Transaction(
            id=f"SINTETICO-COMPARACAO-{index}",
            account_id="TESTE-SINTETICO-COMPARACAO",
            description="Lançamento fictício para teste de centavos",
            amount=amount,
            date=date(2026, 11, 1),
            type=kind,
        )
        for index, (amount, kind) in enumerate(
            [
                (0.10, TransactionType.CREDIT),
                (0.20, TransactionType.CREDIT),
                (0.10, TransactionType.DEBIT),
            ]
        )
    ]
    return CalculationService.calculate_summary(transactions).model_dump()
