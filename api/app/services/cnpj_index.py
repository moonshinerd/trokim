"""Índice local CNPJ → categoria, gerado dos dados abertos da Receita Federal (ADR 0020).

O índice é opcional e fica fora do git (`api/data/cnpj/`, ~130 MB): `make cnpj-index` o gera a
partir dos arquivos de Estabelecimentos baixados uma vez. São dois vetores do mesmo tamanho:
``raizes.npy`` (raiz do CNPJ, 8 dígitos, ordenada) e ``categorias.npy`` (posição da categoria
em :data:`CODES`). Os arquivos são abertos por memory-map: a consulta lê só as páginas da
busca binária, sem carregar o índice na memória. Sem o índice, nada muda.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.domain.models import TransactionCategory

# Ordem fixa: o índice guarda a posição, não o texto. Só se acrescenta no fim.
CODES: list[TransactionCategory] = [
    TransactionCategory.OTHER,
    TransactionCategory.HOUSING,
    TransactionCategory.FOOD,
    TransactionCategory.TRANSPORT,
    TransactionCategory.HEALTH,
    TransactionCategory.EDUCATION,
    TransactionCategory.LEISURE,
    TransactionCategory.SERVICES,
    TransactionCategory.TAXES,
]


class CnpjCategoryIndex:
    def __init__(self, directory: Path) -> None:
        self.roots = np.load(directory / "raizes.npy", mmap_mode="r")
        self.codes = np.load(directory / "categorias.npy", mmap_mode="r")
        if self.roots.shape != self.codes.shape:
            raise ValueError("Índice CNPJ inconsistente: vetores de tamanhos diferentes.")

    def __len__(self) -> int:
        return int(self.roots.shape[0])

    def lookup(self, cnpj: str | None) -> TransactionCategory | None:
        """Categoria pela raiz do CNPJ (14 dígitos); ``None`` se ausente ou sem categoria."""
        digits = "".join(ch for ch in cnpj or "" if ch.isdigit())
        if len(digits) != 14:
            return None
        root = int(digits[:8])
        pos = int(np.searchsorted(self.roots, root))
        if pos >= len(self) or int(self.roots[pos]) != root:
            return None
        category = CODES[int(self.codes[pos])]
        return None if category == TransactionCategory.OTHER else category


@lru_cache(maxsize=1)
def get_index() -> CnpjCategoryIndex | None:
    directory = settings.cnpj_index_dir
    if not (directory / "raizes.npy").exists():
        return None
    try:
        return CnpjCategoryIndex(directory)
    except (OSError, ValueError):
        return None
