"""Acerto da categorização em formatos de vários bancos e adquirentes (#80).

``categorizacao_variacoes`` acompanhou o ajuste das regras (mede regressão);
``categorizacao_holdout`` foi escrito sem olhar as regras (estima o acerto em textos novos).
A meta da #80 é 80%.
"""

import pytest

from app.domain.models import TransactionCategory, TransactionType
from app.services.categorization_service import CategorizationService
from tests.data import categorizacao_holdout, categorizacao_variacoes

META = 0.80


def _acerto(casos: list[tuple[str, str, str]]) -> tuple[float, list[tuple[str, str, str]]]:
    erros = []
    for texto, tipo, esperado in casos:
        tx_type = TransactionType.DEBIT if tipo == "D" else TransactionType.CREDIT
        obtido = CategorizationService.categorize(texto, tx_type=tx_type).value
        if obtido != esperado:
            erros.append((texto, esperado, obtido))
    return 1 - len(erros) / len(casos), erros


@pytest.mark.parametrize(
    ("conjunto", "minimo"),
    [(categorizacao_variacoes, 0.95), (categorizacao_holdout, META)],
    ids=["variacoes", "holdout"],
)
def test_acerto_minimo(conjunto, minimo):
    acerto, erros = _acerto(conjunto.CASOS)
    assert acerto >= minimo, f"acerto {acerto:.1%} < {minimo:.0%}; erros: {erros[:10]}"


def test_conjuntos_usam_so_categorias_existentes():
    validas = {c.value for c in TransactionCategory}
    for conjunto in (categorizacao_variacoes, categorizacao_holdout):
        assert {esperado for *_, esperado in conjunto.CASOS} <= validas


@pytest.mark.parametrize(
    "texto",
    ["TOTALPASS PLANO", "WELLHUB GYMPASS", "BODYTECH MOEMA", "BIO RITMO", "SMART FIT"],
)
def test_academias_ficam_em_saude(texto):
    obtido = CategorizationService.categorize(texto, tx_type=TransactionType.DEBIT)
    assert obtido.value == "saude"


def test_imposto_so_vale_para_saida():
    saida = CategorizationService.categorize("DARF RECEITA FEDERAL", tx_type=TransactionType.DEBIT)
    entrada = CategorizationService.categorize("INSS BENEFICIO", tx_type=TransactionType.CREDIT)
    assert (saida.value, entrada.value) == ("impostos", "renda")
