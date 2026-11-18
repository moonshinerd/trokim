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


class TransactionNature(StrEnum):
    """Natureza do lançamento: separa gasto real de movimentação de dinheiro."""

    PURCHASE = "compra"
    PIX_OUT = "pix_enviado"
    PIX_IN = "pix_recebido"
    CARD_PAYMENT = "pagamento_fatura"
    INVESTMENT_REDEEM = "resgate_investimento"
    INVESTMENT_APPLY = "aplicacao_investimento"
    INTERNAL_TRANSFER = "transferencia_propria"
    REFUND = "estorno"
    FEE = "tarifa"
    INTEREST = "juros"
    OTHER = "outro"


# Movimentações que não são receita nem despesa: ficam fora dos totais para
# não contar duas vezes (ex.: pagar a fatura na conta e importar a fatura).
NATURES_EXCLUDED_FROM_TOTALS: frozenset[TransactionNature] = frozenset(
    {
        TransactionNature.CARD_PAYMENT,
        TransactionNature.INVESTMENT_REDEEM,
        TransactionNature.INVESTMENT_APPLY,
        TransactionNature.INTERNAL_TRANSFER,
    }
)


class CounterpartyKind(StrEnum):
    PERSON = "pessoa"
    COMPANY = "empresa"


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
    nature: TransactionNature = TransactionNature.OTHER
    merchant: str | None = None
    counterparty_kind: CounterpartyKind | None = None
    installment_number: int | None = None
    installment_total: int | None = None
    institution: str | None = None

    @property
    def counts_in_totals(self) -> bool:
        return not self.is_duplicate and self.nature not in NATURES_EXCLUDED_FROM_TOTALS


class FinancialSummary(BaseModel):
    total_income: float = 0.0
    total_expenses: float = 0.0
    net_balance: float = 0.0
    savings_rate: float = 0.0
    expenses_by_category: dict[str, float] = Field(default_factory=dict)
    transaction_count: int = 0
    excluded_count: int = 0  # pagamentos de fatura, resgates e transferências próprias
    top_merchants: list[dict[str, object]] = Field(default_factory=list)


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
