"""Biblioteca local da sessão: lançamentos, arquivos, contas e decisões do usuário.

Fica na memória da API (ADR 0015). ``transactions`` é a mesma lista usada pelo roteador de
lançamentos; ela é limpa no lugar para que referências antigas continuem válidas.
"""

from dataclasses import dataclass, field

from app.domain.models import (
    Account,
    Statement,
    Transaction,
    TransactionCategory,
    TransactionNature,
)


@dataclass(frozen=True)
class Identity:
    """Nome (e documento) de uma conta própria do usuário, aprendido ao confirmar uma
    transferência entre contas."""

    name_norm: str
    doc: str | None = None


@dataclass
class ConfirmedTransfer:
    debit_uid: str
    credit_uid: str
    identities: list[Identity] = field(default_factory=list)


@dataclass
class Library:
    transactions: list[Transaction] = field(default_factory=list)
    statements: dict[str, Statement] = field(default_factory=dict)
    accounts: dict[str, Account] = field(default_factory=dict)
    rejected_pairs: set[str] = field(default_factory=set)
    confirmed: dict[str, ConfirmedTransfer] = field(default_factory=dict)
    # Natureza e categoria originais dos lançamentos marcados como transferência própria,
    # para poder desfazer.
    own_marks: dict[str, tuple[TransactionNature, TransactionCategory]] = field(
        default_factory=dict
    )
    # Lançamentos que o usuário disse que NÃO são transferência entre contas próprias.
    not_own: set[str] = field(default_factory=set)

    def identities(self) -> list[Identity]:
        found: list[Identity] = []
        for transfer in self.confirmed.values():
            for identity in transfer.identities:
                if identity not in found:
                    found.append(identity)
        return found

    def reset(self) -> None:
        self.transactions.clear()
        self.statements.clear()
        self.accounts.clear()
        self.rejected_pairs.clear()
        self.confirmed.clear()
        self.own_marks.clear()
        self.not_own.clear()


LIBRARY = Library()
