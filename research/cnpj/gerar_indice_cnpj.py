"""Gera o índice CNPJ → categoria e o dicionário de marcas a partir dos dados abertos do CNPJ.

Fonte: Receita Federal, "Dados Abertos do CNPJ" (arquivos ``Estabelecimentos*.zip``), baixados
uma vez para uma pasta fora do repositório. Ver ``docs/adr/0020-categorizacao-por-cnae.md``.

Saídas:

- ``api/data/cnpj/raizes.npy`` e ``categorias.npy`` (fora do git): raiz do CNPJ de cada
  empresa ativa e a categoria da atividade principal da matriz (CNAE → ``cnae_categories``).
- ``api/app/data/marcas_cnpj.json`` (versionado): nomes fantasia de **redes** (raiz com muitos
  estabelecimentos ativos sob o mesmo nome) e a categoria. MEI e empresário individual não
  entram: têm um estabelecimento só, e o nome deles costuma ser o de uma pessoa.

Uso, na pasta ``api/`` (lê os zips em fluxo, sem descompactar; pico de memória ~0,5 GB):

    uv run python ../research/cnpj/gerar_indice_cnpj.py --origem ~/dados/receita-cnpj/2026-11
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import zipfile
from array import array
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from app.domain.models import TransactionCategory  # noqa: E402
from app.services.cnae_categories import category_for_cnae  # noqa: E402
from app.services.cnpj_index import CODES  # noqa: E402
from app.services.statement_profiles import normalize_text  # noqa: E402

# Layout de Estabelecimentos (dicionário de dados da Receita).
CNPJ_BASICO, MATRIZ_FILIAL, NOME_FANTASIA, SITUACAO, CNAE_PRINCIPAL = 0, 3, 4, 5, 11
ATIVA = "02"
CODE_OF = {category: code for code, category in enumerate(CODES)}

# Palavras que sozinhas não identificam uma rede (o nome precisa ter algo além delas).
GENERICAS = set(
    """
    a o as os e de da do das dos em no na nos nas com para por the and of
    loja lojas filial matriz unidade centro center shopping posto auto farmacia farmacias
    drogaria drogarias supermercado supermercados mercado mercados atacado atacadao varejo
    comercio comercial servicos servico brasil brasileira brasileiro nacional industria
    restaurante lanchonete padaria bar cafe pizzaria hotel pousada escola colegio clinica
    laboratorio hospital academia oficina transportes transporte distribuidora ltda sa me epp
    eireli cia companhia grupo rede express prime premium top plus mais super mega novo nova
    sao santa santo bom boa vida casa sul norte leste oeste central popular moda store shop
    """.split()
)


def normalizar(nome: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_text(nome)).strip()


def nome_valido(nome: str) -> bool:
    tokens = nome.split()
    if not tokens or len(nome) < 4:
        return False
    significativos = [t for t in tokens if t not in GENERICAS and not t.isdigit() and len(t) > 2]
    if not significativos:
        return False
    # Uma palavra só precisa ser longa o bastante para não ser um termo comum.
    return len(tokens) > 1 or len(tokens[0]) >= 5


def linhas(zips: list[Path]):
    for path in zips:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                with z.open(name) as raw:
                    texto = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                    yield from csv.reader(texto, delimiter=";")


def primeira_passada(zips: list[Path]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Raízes ativas (com repetição) e, para as matrizes ativas, raiz e categoria."""
    ativos = array("I")
    matriz_raiz = array("I")
    matriz_cat = array("B")
    t0 = time.time()
    for n, row in enumerate(linhas(zips), 1):
        if row[SITUACAO] != ATIVA:
            continue
        raiz = int(row[CNPJ_BASICO])
        ativos.append(raiz)
        if row[MATRIZ_FILIAL] == "1":
            matriz_raiz.append(raiz)
            matriz_cat.append(CODE_OF[category_for_cnae(row[CNAE_PRINCIPAL])])
        if n % 5_000_000 == 0:
            print(f"  1ª passada: {n / 1e6:.0f} mi linhas, {time.time() - t0:.0f} s", flush=True)
    return (
        np.frombuffer(ativos, dtype=np.uint32),
        np.frombuffer(matriz_raiz, dtype=np.uint32),
        np.frombuffer(matriz_cat, dtype=np.uint8),
    )


def segunda_passada(zips: list[Path], redes: set[int]) -> Counter:
    """Contagem de (raiz, nome fantasia normalizado) só nas redes."""
    contagem: Counter = Counter()
    t0 = time.time()
    for n, row in enumerate(linhas(zips), 1):
        if row[SITUACAO] != ATIVA or not row[NOME_FANTASIA].strip():
            continue
        raiz = int(row[CNPJ_BASICO])
        if raiz in redes:
            contagem[(raiz, normalizar(row[NOME_FANTASIA]))] += 1
        if n % 5_000_000 == 0:
            print(f"  2ª passada: {n / 1e6:.0f} mi linhas, {time.time() - t0:.0f} s", flush=True)
    return contagem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origem", type=Path, required=True, help="Pasta com Estabelecimentos*.zip"
    )
    parser.add_argument("--indice", type=Path, default=ROOT / "api/data/cnpj")
    parser.add_argument("--marcas", type=Path, default=ROOT / "api/app/data/marcas_cnpj.json")
    parser.add_argument(
        "--min-filiais", type=int, default=20, help="Estabelecimentos ativos da rede com o nome"
    )
    args = parser.parse_args(argv)

    zips = sorted(args.origem.expanduser().glob("Estabelecimentos*.zip"))
    if len(zips) != 10:
        print(f"Esperava 10 arquivos Estabelecimentos*.zip, achei {len(zips)}.", file=sys.stderr)
        return 2

    print("1ª passada: empresas ativas e atividade da matriz")
    ativos, raizes, categorias = primeira_passada(zips)
    ordem = np.argsort(raizes, kind="stable")
    raizes, categorias = raizes[ordem], categorias[ordem]
    unicas = np.concatenate(([True], raizes[1:] != raizes[:-1]))  # uma matriz por raiz
    raizes, categorias = raizes[unicas], categorias[unicas]
    args.indice.mkdir(parents=True, exist_ok=True)
    np.save(args.indice / "raizes.npy", raizes)
    np.save(args.indice / "categorias.npy", categorias)
    tamanho = sum(p.stat().st_size for p in args.indice.glob("*.npy")) / 2**20
    print(f"Índice: {len(raizes):,} empresas ativas, {tamanho:.0f} MB em {args.indice}")

    valores, contagens = np.unique(ativos, return_counts=True)
    redes = set(valores[contagens >= args.min_filiais].tolist())
    del ativos, valores, contagens
    print(f"Redes com {args.min_filiais}+ estabelecimentos ativos: {len(redes):,}")

    print("2ª passada: nomes fantasia das redes")
    contagem = segunda_passada(zips, redes)
    # Só as redes viram dicionário (o índice inteiro como dict passaria de 2 GB).
    redes_arr = np.array(sorted(redes), dtype=np.uint32)
    pos = np.searchsorted(raizes, redes_arr)
    achou = pos < len(raizes)
    achou[achou] = raizes[pos[achou]] == redes_arr[achou]
    categoria_da_raiz = dict(
        zip(redes_arr[achou].tolist(), categorias[pos[achou]].tolist(), strict=True)
    )
    por_nome: dict[str, set[int]] = defaultdict(set)
    for (raiz, nome), n in contagem.items():
        if n >= args.min_filiais and nome_valido(nome):
            codigo = categoria_da_raiz.get(raiz)
            if codigo is not None:
                por_nome[nome].add(codigo)
    marcas = {
        nome: CODES[next(iter(codigos))].value
        for nome, codigos in sorted(por_nome.items())
        if len(codigos) == 1 and CODES[next(iter(codigos))] != TransactionCategory.OTHER
    }
    ambiguas = sum(len(c) > 1 for c in por_nome.values())
    args.marcas.parent.mkdir(parents=True, exist_ok=True)
    args.marcas.write_text(
        json.dumps(
            {
                "fonte": "Receita Federal, Dados Abertos do CNPJ (Estabelecimentos)",
                "referencia": args.origem.expanduser().name,
                "criterio": (
                    f"nome fantasia com {args.min_filiais}+ estabelecimentos ativos da mesma "
                    "raiz; categoria pela atividade principal (CNAE) da matriz; nomes com "
                    "mais de uma categoria entre redes e nomes genéricos ficam de fora"
                ),
                "total": len(marcas),
                "marcas": marcas,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Marcas: {len(marcas):,} (ambíguas descartadas: {ambiguas}) em {args.marcas}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
