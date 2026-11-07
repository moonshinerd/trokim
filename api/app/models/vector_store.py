"""Port abstrato para o banco vetorial persistente."""

from typing import Protocol

from app.domain.models import EvidenceChunk


class VectorStore(Protocol):
    """Contrato de armazenamento vetorial de chunks de evidência."""

    def reset(self) -> None:
        """Remove todos os chunks e metadados de índice."""
        ...

    def add(self, chunks: list[EvidenceChunk], vectors: list[list[float]]) -> None:
        """Insere chunks e seus vetores normalizados (mesma ordem)."""
        ...

    def search(self, vector: list[float], k: int) -> list[tuple[EvidenceChunk, float]]:
        """Retorna os k chunks mais próximos do vetor, com similaridade."""
        ...

    def count(self) -> int:
        """Número de chunks indexados."""
        ...

    def all(self) -> list[EvidenceChunk]:
        """Lista todos os chunks indexados, na ordem de inserção."""
        ...

    def get_meta(self, key: str) -> str | None:
        """Lê um metadado do índice (ex.: hash do corpus, modelo)."""
        ...

    def set_meta(self, key: str, value: str) -> None:
        """Grava um metadado do índice."""
        ...
