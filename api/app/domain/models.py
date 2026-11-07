from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class TransactionType(StrEnum):
    CREDIT = "credit"  # Receita
    DEBIT = "debit"  # Despesa


class TransactionCategory(StrEnum):
    HOUSING = "moradia"
    FOOD = "alimentacao"
    TRANSPORT = "transporte"
    HEALTH = "saude"
    EDUCATION = "educacao"
    LEISURE = "lazer"
    SERVICES = "servicos"
    INCOME = "renda"
    OTHER = "outros"


class Transaction(BaseModel):
    id: str | None = None
    account_id: str
    description: str
    amount: float
    date: date
    type: TransactionType
    category: TransactionCategory = TransactionCategory.OTHER
    source_file: str | None = None
    is_duplicate: bool = False


class FinancialSummary(BaseModel):
    total_income: float = 0.0
    total_expenses: float = 0.0
    net_balance: float = 0.0
    savings_rate: float = 0.0
    expenses_by_category: dict[str, float] = Field(default_factory=dict)
    transaction_count: int = 0


class BudgetScenario(BaseModel):
    name: str
    monthly_income: float
    fixed_expenses: float
    variable_expenses: float
    target_savings: float
    projected_margin: float
    notes: str | None = None


class EvidenceChunk(BaseModel):
    id: str
    document_id: str = ""  # nome do arquivo de origem, ex.: "bcb_orcamento.txt"
    source_name: str  # ex.: "Banco Central do Brasil", "CVM", "CFPB"
    source_url: str | None = None
    document_title: str
    section: str
    content: str
    score: float = 0.0
