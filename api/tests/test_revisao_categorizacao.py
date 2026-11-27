"""Regressões da revisão da Entrega 4: falsos positivos da categorização e da limpeza de nomes."""

import pytest

from app.domain.models import (
    CounterpartyKind,
    TransactionCategory,
    TransactionNature,
    TransactionType,
)
from app.services.categorization_service import CategorizationService
from app.services.statement_profiles import NubankProfile, strip_documents

C = TransactionCategory
DEBIT = TransactionType.DEBIT


def _cat(texto: str, **kwargs) -> TransactionCategory:
    return CategorizationService.categorize(texto, tx_type=DEBIT, **kwargs)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("DROGARIA EXTRA", C.HEALTH),
        ("FARMACIA FEIRA DE SANTANA", C.HEALTH),
        ("DROGARIA UNIDAS", C.HEALTH),
        ("UNIDAS LOCADORA", C.TRANSPORT),
        ("UBER EATS", C.FOOD),
        ("SUPERMERCADO EXTRA", C.FOOD),
        ("CARREFOUR COM IND LTDA", C.FOOD),
    ],
)
def test_extras_nao_passam_na_frente_de_outras_categorias(texto, esperado):
    assert _cat(texto) == esperado


@pytest.mark.parametrize(
    "nome", ["CARLOS BRETAS", "MARIA FUJIOKA", "MARISA SOUZA", "JOAO VENANCIO"]
)
def test_pix_para_pessoa_nao_vira_rede_pelo_sobrenome(nome):
    categoria = _cat(
        nome, nature=TransactionNature.PIX_OUT, counterparty_kind=CounterpartyKind.PERSON
    )
    assert categoria == C.OTHER


def test_pix_para_empresa_ainda_usa_os_termos_extras():
    categoria = _cat(
        "DROGARIA VENANCIO",
        nature=TransactionNature.PIX_OUT,
        counterparty_kind=CounterpartyKind.COMPANY,
    )
    assert categoria == C.HEALTH


def test_internetbanking_nao_vira_moradia():
    assert _cat("PAGAMENTO INTERNETBANKING") == C.OTHER


@pytest.mark.parametrize(
    ("nome", "limpo"),
    [
        ("PADARIA SOL 12345678000190", "PADARIA SOL"),
        ("PADARIA SOL 12.345.678/0001-90", "PADARIA SOL"),
        ("JOAO SILVA 12345678909", "JOAO SILVA"),
        ("JOAO SILVA 123.456.789-09", "JOAO SILVA"),
        ("12.345.678 MARIA LANCHES", "MARIA LANCHES"),
        ("LOJA 123456789012345", "LOJA 123456789012345"),
    ],
)
def test_strip_documents_tira_o_documento_inteiro(nome, limpo):
    assert strip_documents(nome) == limpo


def test_boleto_de_fatura_de_outro_banco_nao_e_gasto():
    parsed = NubankProfile().parse(
        "Pagamento de boleto efetuado - BANCO ITAUCARD S.A.", DEBIT, "conta"
    )
    assert parsed.nature == TransactionNature.CARD_PAYMENT


def test_boleto_de_conta_de_consumo_continua_compra():
    parsed = NubankProfile().parse("Pagamento de boleto efetuado - ENEL SP", DEBIT, "conta")
    assert parsed.nature == TransactionNature.PURCHASE
