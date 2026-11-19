"""Gerador do índice CNPJ → categoria e do dicionário de marcas, com zips sintéticos."""

import importlib.util
import json
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gerar_indice_cnpj", ROOT / "research/cnpj/gerar_indice_cnpj.py"
)
gerador = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gerador)


def _linha(raiz, ordem, matriz, fantasia, situacao, cnae):
    campos = [f"{raiz:08d}", f"{ordem:04d}", "00", matriz, fantasia, situacao]
    campos += ["20200101", "00", "", "", "20200101", cnae, ""] + [""] * 17
    return ";".join(f'"{c}"' for c in campos)


def _zips(pasta: Path) -> None:
    linhas = [
        # Rede de mercados: matriz + 2 filiais com o mesmo nome fantasia.
        _linha(11111111, 1, "1", "MERCADOS EXEMPLAR", "02", "4711302"),
        _linha(11111111, 2, "2", "MERCADOS EXEMPLAR", "02", "4711302"),
        _linha(11111111, 3, "2", "MERCADOS EXEMPLAR", "02", "4711302"),
        # Empresa única de indústria (fica fora do dicionário e vira "outros" no índice).
        _linha(22222222, 1, "1", "FABRICA", "02", "2512800"),
        # Baixada: não entra.
        _linha(33333333, 1, "1", "LOJA FECHADA", "08", "4781400"),
        # Rede cuja matriz é escritório (CNAE 7020) e as lojas são mercados: no índice vale a
        # matriz ("outros"); no dicionário, a atividade mais comum das lojas.
        _linha(55555555, 1, "1", "SUPER EXEMPLO", "02", "7020400"),
        _linha(55555555, 2, "2", "SUPER EXEMPLO", "02", "4711302"),
        _linha(55555555, 3, "2", "SUPER EXEMPLO", "02", "4711302"),
        # Rede com nome só genérico: entra no índice, não no dicionário.
        _linha(44444444, 1, "1", "FARMACIA", "02", "4771701"),
        _linha(44444444, 2, "2", "FARMACIA", "02", "4771701"),
        _linha(44444444, 3, "2", "FARMACIA", "02", "4771701"),
    ]
    for i in range(10):
        with zipfile.ZipFile(pasta / f"Estabelecimentos{i}.zip", "w") as z:
            conteudo = "\n".join(linhas) + "\n" if i == 0 else ""
            z.writestr(f"K{i}.ESTABELE", conteudo.encode("latin-1"))


def test_gera_indice_e_marcas_sem_genericos_nem_baixadas(tmp_path):
    origem, indice, marcas = tmp_path / "origem", tmp_path / "indice", tmp_path / "marcas.json"
    pacote = tmp_path / "pacote.xz"
    origem.mkdir()
    _zips(origem)
    saida = gerador.main(
        [
            "--origem",
            str(origem),
            "--indice",
            str(indice),
            "--marcas",
            str(marcas),
            "--pacote",
            str(pacote),
            "--min-filiais",
            "3",
        ]
    )
    assert saida == 0
    raizes = np.load(indice / "raizes.npy")
    categorias = np.load(indice / "categorias.npy")
    # Só as empresas com categoria entram (indústria e escritório ficam de fora).
    assert raizes.tolist() == [11111111, 44444444]
    nomes = [gerador.CODES[c].value for c in categorias]
    assert nomes == ["alimentacao", "saude"]
    manifesto = json.loads(pacote.with_suffix(".json").read_text(encoding="utf-8"))
    assert manifesto["empresas_ativas"] == 4
    assert manifesto["empresas_com_categoria"] == 2
    assert manifesto["referencia"] == "origem"
    dados = json.loads(marcas.read_text(encoding="utf-8"))
    assert dados["marcas"] == {
        "mercados exemplar": "alimentacao",
        "super exemplo": "alimentacao",
    }


def test_nome_valido_recusa_termos_genericos():
    assert gerador.nome_valido("mercados exemplar")
    assert gerador.nome_valido("zaffari")
    assert not gerador.nome_valido("farmacia")
    assert not gerador.nome_valido("posto central")
    assert not gerador.nome_valido("abc")
    assert not gerador.nome_valido("avenida")
    assert not gerador.nome_valido("diretoria regional de alagoas")
    assert not gerador.nome_valido("condominio residencial multifamiliar")
