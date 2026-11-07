"""Port abstrato para modelos de embeddings densos."""

from typing import Protocol


class EmbeddingModel(Protocol):
    """Contrato de um modelo local de embeddings.

    Vetores devem sair normalizados, de modo que similaridade de cosseno
    coincida com o produto interno.
    """

    name: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings para uma lista de textos de documentos/chunks."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Gera o embedding de uma consulta."""
        ...
