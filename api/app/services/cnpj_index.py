"""Índice local CNPJ → categoria, gerado dos dados abertos da Receita Federal (ADR 0020).

Duas formas do mesmo índice:

- **Pacote versionado** (`api/app/data/cnpj_categorias.xz`, ~14 MB, no git): raízes ordenadas
  guardadas como diferença para a anterior e categorias, comprimidas com xz. Só entram as
  empresas com categoria; quem não está no pacote fica sem categoria, como "outros".
- **Índice de consulta** (`api/data/cnpj/`, ~100 MB, fora do git): ``raizes.npy`` (raiz do CNPJ,
  8 dígitos, ordenada) e ``categorias.npy`` (posição em :data:`CODES`), abertos por
  memory-map, sem carregar na memória.

O índice de consulta sai do pacote: `make build` descomprime, e :func:`ensure_unpacked` faz o
mesmo no primeiro uso se faltar ou se o pacote mudou (``origem.json`` guarda o hash do pacote).
`make cnpj-atualizar` refaz o pacote a partir de um mês novo da Receita.
"""

import hashlib
import json
import lzma
import os
import struct
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


PACK_FILE = Path(__file__).resolve().parents[1] / "data" / "cnpj_categorias.xz"
_MAGIC = b"TROKIM-CNPJ-1\n"
_STAMP = "origem.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def pack(roots: np.ndarray, codes: np.ndarray, path: Path) -> int:
    """Grava o pacote com as empresas que têm categoria; devolve quantas entraram."""
    roots = np.asarray(roots, dtype=np.uint32)
    codes = np.asarray(codes, dtype=np.uint8)
    if roots.shape != codes.shape or (roots.size and np.any(np.diff(roots.astype(np.int64)) <= 0)):
        raise ValueError("Raízes precisam ser únicas, ordenadas e do tamanho das categorias.")
    keep = codes != CODES.index(TransactionCategory.OTHER)
    roots, codes = roots[keep], codes[keep]
    deltas = np.diff(roots, prepend=np.uint32(0)).astype("<u4")
    payload = _MAGIC + struct.pack("<I", roots.size) + deltas.tobytes() + codes.tobytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(lzma.compress(payload, preset=6))
    os.replace(temp, path)
    return int(roots.size)


def unpack(path: Path) -> tuple[np.ndarray, np.ndarray]:
    payload = lzma.decompress(path.read_bytes())
    if not payload.startswith(_MAGIC):
        raise ValueError("Pacote do índice CNPJ em formato desconhecido.")
    start = len(_MAGIC)
    (count,) = struct.unpack_from("<I", payload, start)
    start += 4
    deltas = np.frombuffer(payload, dtype="<u4", count=count, offset=start)
    codes = np.frombuffer(payload, dtype=np.uint8, count=count, offset=start + 4 * count)
    if start + 5 * count != len(payload) or (count and int(codes.max()) >= len(CODES)):
        raise ValueError("Pacote do índice CNPJ corrompido.")
    roots = np.cumsum(deltas, dtype=np.uint64).astype(np.uint32)
    return roots, codes.copy()


def ensure_unpacked(directory: Path, pack_file: Path = PACK_FILE) -> bool:
    """Descomprime o pacote em ``directory`` se faltar o índice ou se o pacote mudou.

    Devolve se há índice para consultar. Sem pacote, vale o que já estiver na pasta.
    """
    roots_file, stamp_file = directory / "raizes.npy", directory / _STAMP
    if not pack_file.exists():
        return roots_file.exists()
    digest = sha256_file(pack_file)
    try:
        current = json.loads(stamp_file.read_text(encoding="utf-8")).get("pacote_sha256")
    except (OSError, ValueError):
        current = None
    if current == digest and roots_file.exists() and (directory / "categorias.npy").exists():
        return True
    roots, codes = unpack(pack_file)
    directory.mkdir(parents=True, exist_ok=True)
    for name, array in (("raizes.npy", roots), ("categorias.npy", codes)):
        temp = directory / f".{name}.{os.getpid()}.tmp"
        with temp.open("wb") as handle:
            np.save(handle, array)
        os.replace(temp, directory / name)
    stamp_file.write_text(
        json.dumps({"pacote_sha256": digest, "empresas": int(roots.size)}) + "\n",
        encoding="utf-8",
    )
    return True


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
    try:
        if not ensure_unpacked(directory):
            return None
        return CnpjCategoryIndex(directory)
    except (OSError, ValueError, lzma.LZMAError):
        return None


def main() -> int:
    """``python -m app.services.cnpj_index``: descomprime o pacote (usado por ``make build``)."""
    import time

    directory = settings.cnpj_index_dir
    if not PACK_FILE.exists():
        print(f"Sem pacote em {PACK_FILE}: a categorização por CNPJ fica desligada.")
        return 0
    start = time.perf_counter()
    ensure_unpacked(directory)
    index = CnpjCategoryIndex(directory)
    print(
        f"Índice CNPJ pronto em {directory}: {len(index):,} empresas com categoria "
        f"({time.perf_counter() - start:.1f} s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
