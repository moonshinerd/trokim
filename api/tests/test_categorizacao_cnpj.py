"""Categorização por atividade (CNAE): índice CNPJ e dicionário de redes (ADR 0020)."""

import numpy as np
import pytest

from app.domain.models import TransactionCategory as C
from app.domain.models import TransactionType
from app.services import categorization_service as cs
from app.services import cnpj_index
from app.services.cnae_categories import category_for_cnae
from app.services.cnpj_index import CODES, CnpjCategoryIndex

D = TransactionType.DEBIT


@pytest.mark.parametrize(
    ("cnae", "categoria"),
    [
        ("5611-2/01", C.FOOD),  # restaurante
        ("4711302", C.FOOD),  # supermercado
        ("4731800", C.TRANSPORT),  # posto de combustível
        ("4771701", C.HEALTH),  # farmácia
        ("9313100", C.HEALTH),  # academia
        ("8513900", C.EDUCATION),  # ensino fundamental
        ("5510801", C.LEISURE),  # hotel
        ("4789004", C.LEISURE),  # pet shop (subclasse vence a classe 4789)
        ("4789099", C.SERVICES),  # outros varejos
        ("6550200", C.HEALTH),  # plano de saúde (classe vence a divisão 65)
        ("8411600", C.TAXES),  # administração pública
        ("4639701", C.OTHER),  # atacado: não diz nada sobre o gasto
        (None, C.OTHER),
    ],
)
def test_cnae_vira_categoria_pelo_prefixo_mais_longo(cnae, categoria):
    assert category_for_cnae(cnae) == categoria


@pytest.fixture
def indice(tmp_path, monkeypatch):
    np.save(tmp_path / "raizes.npy", np.array([11111111, 22222222, 33333333], dtype=np.uint32))
    codigos = [CODES.index(C.FOOD), CODES.index(C.OTHER), CODES.index(C.TAXES)]
    np.save(tmp_path / "categorias.npy", np.array(codigos, dtype=np.uint8))
    idx = CnpjCategoryIndex(tmp_path)
    monkeypatch.setattr(cnpj_index, "get_index", lambda: idx)
    return idx


def test_indice_consulta_pela_raiz_do_cnpj(indice):
    assert indice.lookup("11.111.111/0042-99") == C.FOOD  # filial vale a atividade da matriz
    assert indice.lookup("22222222000100") is None  # atividade sem categoria
    assert indice.lookup("99999999000100") is None  # fora do índice
    assert indice.lookup("123.456.789-00") is None  # CPF nunca é consultado


def test_cnpj_so_entra_quando_as_regras_nao_reconhecem(indice):
    cat = cs.CategorizationService.categorize
    assert cat("Fulano Comercio", tx_type=D, cnpj="11111111000199") == C.FOOD
    assert cat("Uber Trip", tx_type=D, cnpj="11111111000199") == C.TRANSPORT  # regra vence
    assert cat("Fulano Comercio", tx_type=D) == C.OTHER  # sem CNPJ
    # Entrada nunca vira imposto nem gasto pela atividade de quem pagou.
    entrada = cat("Prefeitura", tx_type=TransactionType.CREDIT, cnpj="33333333000100")
    assert entrada == C.INCOME


def test_sem_indice_nada_muda(monkeypatch):
    monkeypatch.setattr(cnpj_index, "get_index", lambda: None)
    cat = cs.CategorizationService.categorize("Fulano Comercio", tx_type=D, cnpj="11111111000199")
    assert cat == C.OTHER


def test_dicionario_de_redes_reconhece_nome_dentro_do_texto(monkeypatch):
    marcas = {"mercados exemplar": C.FOOD, "exemplar": C.SERVICES}
    monkeypatch.setattr(cs, "_brands", lambda: (marcas, 2))
    cat = cs.CategorizationService.categorize
    assert cat("PAG*MERCADOS EXEMPLAR 0042", tx_type=D) == C.FOOD  # sequência mais longa vence
    assert cat("Uber Trip", tx_type=D) == C.TRANSPORT  # regras vêm antes do dicionário
    assert cat("MERCADOS EXEMPLAR", tx_type=TransactionType.CREDIT) == C.INCOME
