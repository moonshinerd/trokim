"""Retrato da biblioteca do usuário (domínio puro), usado na persistência local e no backup.

O mesmo formato serve ao SQLite e ao arquivo ``.trokim``. Os campos que a API nunca expõe
(documento e conta da contraparte do Pix) entram aqui porque só servem para reconhecer as
contas próprias do usuário, e o retrato fica no aparelho ou criptografado (ADR 0024).
"""

from pydantic import BaseModel, Field

from app.domain.models import (
    Account,
    Statement,
    Transaction,
    TransactionCategory,
    TransactionNature,
)

SNAPSHOT_VERSION = 1


class StoredTransaction(Transaction):
    """Lançamento com os campos privados que a API normalmente oculta."""

    counterparty_doc: str | None = Field(default=None)
    counterparty_account: str | None = Field(default=None)


class StoredIdentity(BaseModel):
    name_norm: str
    doc: str | None = None


class StoredTransfer(BaseModel):
    debit_uid: str
    credit_uid: str
    identities: list[StoredIdentity] = Field(default_factory=list)
    kind: str = "transferencia"


class StoredOwnMark(BaseModel):
    nature: TransactionNature
    category: TransactionCategory


class LibrarySnapshot(BaseModel):
    version: int = SNAPSHOT_VERSION
    transactions: list[StoredTransaction] = Field(default_factory=list)
    statements: dict[str, Statement] = Field(default_factory=dict)
    accounts: dict[str, Account] = Field(default_factory=dict)
    rejected_pairs: list[str] = Field(default_factory=list)
    confirmed: dict[str, StoredTransfer] = Field(default_factory=dict)
    own_marks: dict[str, StoredOwnMark] = Field(default_factory=dict)
    own_reasons: dict[str, tuple[str, str]] = Field(default_factory=dict)
    not_own: list[str] = Field(default_factory=list)
    category_rules: dict[str, TransactionCategory] = Field(default_factory=dict)
