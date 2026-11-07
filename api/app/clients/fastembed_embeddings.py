"""Adaptador de embeddings densos locais via fastembed (ONNX, sem rede em execução)."""

import math
import os
from functools import lru_cache
from pathlib import Path

from fastembed import TextEmbedding

from app.core.config import settings

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=4)
def _load_model(model_name: str) -> TextEmbedding:
    """Cache de processo: o modelo ONNX é carregado uma única vez por nome."""
    return TextEmbedding(
        model_name=model_name,
        cache_dir=os.environ.get("FASTEMBED_CACHE_PATH", str(Path.home() / ".cache/fastembed")),
        threads=2,
    )


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


class FastEmbedModel:
    """Implementa a port EmbeddingModel usando fastembed.

    Os vetores saem normalizados: similaridade de cosseno = produto interno.
    """

    def __init__(self, model_name: str | None = None):
        self._model = _load_model(model_name or settings.RAG_EMBEDDING_MODEL)
        self.name = model_name or settings.RAG_EMBEDDING_MODEL
        vector = next(iter(self._model.embed(["dimensão"])))
        self.dimension = len(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_normalize(list(v)) for v in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        embed_fn = getattr(self._model, "query_embed", None) or self._model.embed
        return _normalize(list(next(iter(embed_fn([text])))))


@lru_cache(maxsize=1)
def get_default_embedder() -> FastEmbedModel:
    """Instância única por processo do embedder configurado em settings."""
    return FastEmbedModel()
