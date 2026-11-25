import hashlib
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class TransactionType(StrEnum):
    CREDIT = "credit"  # Receita
    DEBIT = "debit"  # Despesa


class TransactionOrigin(StrEnum):
    IMPORT = "importacao"
    DOCUMENT = "documento"


class TransactionCategory(StrEnum):
    HOUSING = "moradia"
    FOOD = "alimentacao"
    TRANSPORT = "transporte"
    HEALTH = "saude"
    EDUCATION = "educacao"
    LEISURE = "lazer"
    SERVICES = "servicos"
    TAXES = "impostos"
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


class AccountKind(StrEnum):
    CHECKING = "conta"
    CARD = "cartao"


class AccountOwner(StrEnum):
    PERSONAL = "pessoal"
    BUSINESS = "empresa"


class StatementStatus(StrEnum):
    """Situação do período do arquivo: completo, ainda aberto ou sem como saber."""

    CLOSED = "fechada"
    OPEN = "aberta"  # fatura de cartão cujo ciclo ainda não terminou
    PARTIAL = "parcial"  # extrato de conta cujo período ainda não terminou
    UNKNOWN = "desconhecida"


class Transaction(BaseModel):
    id: str | None = None
    account_id: str
    description: str
    amount: float
    date: date
    type: TransactionType
    category: TransactionCategory = TransactionCategory.OTHER
    source_file: str | None = None
    origin: TransactionOrigin = TransactionOrigin.IMPORT
    is_duplicate: bool = False
    nature: TransactionNature = TransactionNature.OTHER
    merchant: str | None = None
    counterparty_kind: CounterpartyKind | None = None
    installment_number: int | None = None
    installment_total: int | None = None
    institution: str | None = None
    source_kind: str | None = None  # "cartao" ou "conta", quando o arquivo é de um banco conhecido
    statement_id: str | None = None
    # Documento da contraparte (CNPJ ou CPF mascarado): só serve para reconhecer as
    # próprias contas do usuário. Nunca sai pela API.
    counterparty_doc: str | None = Field(default=None, exclude=True)
    # Banco e conta de destino/origem do Pix ("0260:123456789"): só serve para ligar o
    # lançamento a uma conta que o usuário também importou. Nunca sai pela API.
    counterparty_account: str | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def uid(self) -> str:
        """Identificador estável do lançamento, único entre arquivos e contas."""
        raw = "|".join(
            [
                self.account_id,
                self.id or "",
                self.date.isoformat(),
                f"{self.amount:.2f}",
                self.type.value,
                self.description,
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    @property
    def counts_in_totals(self) -> bool:
        return not self.is_duplicate and self.nature not in NATURES_EXCLUDED_FROM_TOTALS


class Account(BaseModel):
    """Conta ou cartão cadastrado a partir dos arquivos importados."""

    id: str  # "<banco>:<número da conta>"
    institution: str | None = None
    acct_id: str
    kind: AccountKind | None = None
    owner: AccountOwner | None = None  # o OFX não diz se é pessoal ou empresa
    label: str | None = None
    bank_code: str | None = None  # "0260" (compensação), para ligar Pix entre contas

    @property
    def needs_owner(self) -> bool:
        return self.owner is None

    @property
    def link_key(self) -> str | None:
        """Chave que aparece como destino nos Pix de outras contas."""
        digits = "".join(ch for ch in self.acct_id if ch.isdigit())
        return f"{self.bank_code}:{digits}" if self.bank_code and digits else None


class Statement(BaseModel):
    """Um arquivo importado: período, situação e cobertura."""

    id: str
    account_id: str
    filename: str
    kind: AccountKind | None = None
    period_start: date | None = None
    period_end: date | None = None
    generated_at: date | None = None
    status: StatementStatus = StatementStatus.UNKNOWN
    covered_until: date | None = None
    closes_on: date | None = None
    # Vencimento da fatura, quando o arquivo o informa (PDF do Itaú e do PicPay). OFX não traz.
    due_date: date | None = None
    user_confirmed: bool = False
    ledger_balance: float | None = None
    imported_count: int = 0


class FinancialSummary(BaseModel):
    total_income: float = 0.0
    total_expenses: float = 0.0
    net_balance: float = 0.0
    savings_rate: float = 0.0
    expenses_by_category: dict[str, float] = Field(default_factory=dict)
    transaction_count: int = 0
    excluded_count: int = 0  # pagamentos de fatura, resgates e transferências próprias
    view: str = "competencia"
    owner: str = "todas"
    by_account: list[dict[str, object]] = Field(default_factory=list)
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
