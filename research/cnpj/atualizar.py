"""Atualiza o índice CNPJ → categoria e o dicionário de redes com um mês novo da Receita.

Passos: descobre o mês mais recente publicado, mostra o que vai baixar, o espaço em disco, o
tempo e a memória, pede confirmação, baixa (``baixar.sh``), gera o pacote versionado e o
dicionário (``gerar_indice_cnpj.py``) e, no fim, apaga os arquivos baixados. Ver ADR 0020.

Uso, pela raiz do repositório: ``make cnpj-atualizar`` (ou ``MES=2026-11``, ``CONFIRMAR=sim``,
``MANTER_DOWNLOAD=1``).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

SHARE = "gn672Ad4CF8N6TK"
WEBDAV = "https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/"
ARQUIVOS = ["Cnaes.zip"] + [f"Estabelecimentos{i}.zip" for i in range(10)]
MANIFESTO = ROOT / "api/app/data/cnpj_categorias.json"
MES_RE = re.compile(r"/CNPJ/(\d{4}-\d{2})/$")
MARGEM = 1 << 30  # 1 GB além do download


def listar(caminho: str = "") -> list[tuple[str, int]]:
    """(href, tamanho) de cada item da pasta, pelo PROPFIND do compartilhamento público."""
    pedido = urllib.request.Request(WEBDAV + caminho, method="PROPFIND", headers={"Depth": "1"})
    token = base64.b64encode(f"{SHARE}:".encode()).decode()
    pedido.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(pedido, timeout=60) as resposta:
        arvore = ET.fromstring(resposta.read())
    itens = []
    for item in arvore.findall("{DAV:}response"):
        href = item.findtext("{DAV:}href", "")
        tamanho = item.findtext(".//{DAV:}getcontentlength")
        itens.append((href, int(tamanho) if tamanho else 0))
    return itens


def mes_mais_recente() -> str:
    meses = sorted({m.group(1) for href, _ in listar() if (m := MES_RE.search(href))})
    if not meses:
        raise SystemExit("Não achei nenhum mês publicado na Receita.")
    return meses[-1]


def tamanhos(mes: str) -> dict[str, int]:
    nomes = {href.rsplit("/", 1)[-1]: tamanho for href, tamanho in listar(f"{mes}/")}
    faltando = [a for a in ARQUIVOS if a not in nomes]
    if faltando:
        raise SystemExit(f"O mês {mes} ainda não tem: {', '.join(faltando)}.")
    return {a: nomes[a] for a in ARQUIVOS}


def gb(n: float) -> str:
    return f"{n / 2**30:.1f} GB".replace(".", ",")


def referencia_atual() -> str | None:
    try:
        return json.loads(MANIFESTO.read_text(encoding="utf-8")).get("referencia")
    except (OSError, ValueError):
        return None


def apagar_download(destino: Path) -> None:
    """Apaga só os arquivos que o atualizador baixa, e a pasta se ficar vazia."""
    for nome in ARQUIVOS:
        (destino / nome).unlink(missing_ok=True)
    try:
        destino.rmdir()
    except OSError:
        print(f"  {destino} não está vazia; o resto da pasta ficou.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mes", default="", help="AAAA-MM; vazio = o mais recente publicado")
    parser.add_argument("--base", type=Path, default=Path.home() / "dados/receita-cnpj")
    parser.add_argument("--sim", action="store_true", help="Não pede confirmação.")
    parser.add_argument("--manter-download", action="store_true")
    parser.add_argument("--forcar", action="store_true", help="Refaz mesmo se já for o mês atual.")
    args = parser.parse_args(argv)

    mes = args.mes or mes_mais_recente()
    atual = referencia_atual()
    if atual == mes and not args.forcar:
        print(f"O índice versionado já é de {mes}, o mês mais recente. Nada a fazer.")
        print("Para refazer mesmo assim: make cnpj-atualizar FORCAR=1")
        return 0

    por_arquivo = tamanhos(mes)
    destino = args.base.expanduser() / mes
    destino.mkdir(parents=True, exist_ok=True)
    ja_baixado = sum(
        min((destino / a).stat().st_size, t)
        for a, t in por_arquivo.items()
        if (destino / a).exists()
    )
    falta = sum(por_arquivo.values()) - ja_baixado
    livre = shutil.disk_usage(destino).free

    print(
        f"""
Atualização do índice CNPJ -> categoria (dados abertos da Receita Federal)

  Mês: {mes} (versionado hoje: {atual or "nenhum"})
  Vai BAIXAR {gb(sum(por_arquivo.values()))} ({len(ARQUIVOS)} arquivos; falta {gb(falta)}) para:
    {destino}
  Espaço livre nesse disco: {gb(livre)} (precisa de {gb(falta + MARGEM)})
  Tempo: o download depende da conexão (a Receita limita cada conexão a ~0,3 MB/s; são 5
    em paralelo, então conte de 1 a 3 horas); depois, ~40 min de processamento.
  Memória: até ~1,5 GB de RAM durante a geração.
  Vai SUBSTITUIR os arquivos versionados:
    api/app/data/cnpj_categorias.xz e .json (o índice, ~15 MB)
    api/app/data/marcas_cnpj.json (o dicionário de redes)
  {"Vai MANTER" if args.manter_download else "No fim, vai APAGAR"} os arquivos baixados em:
    {destino}
  Empresas e Sócios não são baixados (trazem nomes de pessoas).
"""
    )
    if livre < falta + MARGEM:
        print("Espaço livre insuficiente. Libere espaço ou use CNPJ_BASE=<outra pasta>.")
        return 1
    if not args.sim:
        if not sys.stdin.isatty():
            print("Sem terminal para confirmar. Rode de novo com CONFIRMAR=sim.")
            return 1
        if input("Digite SIM para continuar: ").strip().upper() != "SIM":
            print("Cancelado; nada foi baixado nem alterado.")
            return 1

    baixar = ROOT / "research/cnpj/baixar.sh"
    if subprocess.run([str(baixar), mes, str(destino)], check=False).returncode != 0:
        print(
            f"O download falhou. Os arquivos parciais ficaram em {destino}; "
            "rode de novo para continuar."
        )
        return 1
    for nome, tamanho in por_arquivo.items():
        if (destino / nome).stat().st_size != tamanho:
            print(f"{nome} veio com tamanho diferente do anunciado; rode de novo para continuar.")
            return 1

    import gerar_indice_cnpj  # noqa: E402  (mesma pasta)

    if gerar_indice_cnpj.main(["--origem", str(destino)]) != 0:
        print(f"A geração falhou; os arquivos baixados ficaram em {destino}.")
        return 1

    if not args.manter_download:
        apagar_download(destino)
        print(f"Arquivos baixados apagados de {destino}.")
    print(
        "\nPronto. Confira com `git diff --stat api/app/data`, rode `make test` e registre a"
        " atualização (mês e contagens) na ADR 0020 antes de commitar."
    )
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
