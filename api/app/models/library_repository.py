"""Porta de persistência da biblioteca do usuário (ADR 0024).

Quem usa a biblioteca não sabe onde ela é guardada: hoje é o SQLite da aplicação, e o app
no aparelho poderá guardar do seu jeito sem mudar as regras de negócio.
"""

from abc import ABC, abstractmethod

from app.domain.snapshot import LibrarySnapshot


class LibraryRepository(ABC):
    @abstractmethod
    def load(self) -> LibrarySnapshot | None:
        """Devolve o último retrato gravado, ou ``None`` se ainda não há nenhum."""

    @abstractmethod
    def save(self, snapshot: LibrarySnapshot) -> None:
        """Substitui o retrato gravado pelo novo, de uma vez só."""
