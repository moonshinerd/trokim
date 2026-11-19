"""Pacote versionado do índice CNPJ: compressão, descompressão no primeiro uso e manifesto."""

import json

import numpy as np
import pytest

from app.domain.models import TransactionCategory as C
from app.services import cnpj_index
from app.services.cnpj_index import CODES, PACK_FILE, ensure_unpacked, pack, sha256_file, unpack

OUTROS, SAUDE, LAZER = (CODES.index(c) for c in (C.OTHER, C.HEALTH, C.LEISURE))


def _pacote(tmp_path, raizes=(10, 20, 30_000_000, 99_999_999), codigos=None):
    codigos = codigos or [SAUDE, OUTROS, LAZER, SAUDE]
    arquivo = tmp_path / "pacote.xz"
    n = pack(np.array(raizes, dtype=np.uint32), np.array(codigos, dtype=np.uint8), arquivo)
    return arquivo, n


def test_ida_e_volta_sem_as_empresas_em_outros(tmp_path):
    arquivo, n = _pacote(tmp_path)
    raizes, codigos = unpack(arquivo)
    assert n == 3
    assert raizes.tolist() == [10, 30_000_000, 99_999_999]
    assert codigos.tolist() == [SAUDE, LAZER, SAUDE]


def test_recusa_raizes_fora_de_ordem(tmp_path):
    with pytest.raises(ValueError):
        pack(np.array([5, 3], dtype=np.uint32), np.array([1, 1], dtype=np.uint8), tmp_path / "x")


def test_recusa_pacote_corrompido(tmp_path):
    import lzma

    arquivo = tmp_path / "ruim.xz"
    arquivo.write_bytes(lzma.compress(b"outra coisa"))
    with pytest.raises(ValueError):
        unpack(arquivo)


def test_descomprime_no_primeiro_uso_e_so_de_novo_se_o_pacote_mudar(tmp_path):
    arquivo, _ = _pacote(tmp_path)
    pasta = tmp_path / "indice"
    assert ensure_unpacked(pasta, arquivo)
    indice = cnpj_index.CnpjCategoryIndex(pasta)
    assert indice.lookup("00000010000199") == C.HEALTH
    assert indice.lookup("00000020000199") is None  # estava em "outros"
    antes = (pasta / "raizes.npy").stat().st_mtime_ns

    assert ensure_unpacked(pasta, arquivo)  # mesmo pacote: não reescreve
    assert (pasta / "raizes.npy").stat().st_mtime_ns == antes

    _pacote(tmp_path, raizes=(10,), codigos=[LAZER])  # pacote novo, mesmo caminho
    assert ensure_unpacked(pasta, arquivo)
    assert cnpj_index.CnpjCategoryIndex(pasta).lookup("00000010000199") == C.LEISURE


def test_sem_pacote_vale_o_que_estiver_na_pasta(tmp_path):
    assert not ensure_unpacked(tmp_path / "vazia", tmp_path / "nao-existe.xz")


def test_pacote_versionado_e_pequeno_e_bate_com_o_manifesto():
    manifesto = json.loads(PACK_FILE.with_suffix(".json").read_text(encoding="utf-8"))
    assert PACK_FILE.stat().st_size < 50 * 2**20  # o GitHub avisa acima de 50 MB
    assert manifesto["pacote_sha256"] == sha256_file(PACK_FILE)
    assert manifesto["empresas_com_categoria"] <= manifesto["empresas_ativas"]
    assert manifesto["referencia"]


@pytest.mark.indice_cnpj_real
def test_indice_real_categoriza_uma_rede_conhecida():
    """Raiz pública da RD Saúde (Droga Raia e Drogasil): farmácia, logo saúde."""
    cnpj_index.get_index.cache_clear()
    indice = cnpj_index.get_index()
    assert indice is not None and len(indice) > 1_000_000
    assert indice.lookup("61585865000151") == C.HEALTH
