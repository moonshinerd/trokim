from datetime import date

import pytest

from app.domain.models import TransactionCategory, TransactionType
from app.services.categorization_service import CategorizationService
from app.services.parser_service import ParserService

HOJE = date(2026, 11, 18)


def _um(texto: str, hoje: date = HOJE):
    txs = ParserService.parse_pdf_text(texto, today=hoje)
    assert len(txs) == 1, txs
    return txs[0]


def test_descricao_com_acento_e_lida():
    tx = _um("EXTRATO\n05/11 PADARIA PÃO QUENTE -12,50")
    assert tx.description == "PADARIA PÃO QUENTE"
    assert tx.amount == 12.50
    assert tx.category == TransactionCategory.FOOD


def test_valor_com_milhar_nao_e_truncado():
    assert _um("EXTRATO\n05/11 PIX RECEBIDO JOAO 1.250,00").amount == 1250.00
    assert _um("EXTRATO\n05/11 COMPRA CARTAO 1.234,56-").amount == 1234.56


def test_sinal_a_frente_atras_e_sufixos():
    assert _um("EXTRATO\n05/11 LOJA -R$ 10,00").type == TransactionType.DEBIT
    assert _um("EXTRATO\n05/11 LOJA 10,00-").type == TransactionType.DEBIT
    assert _um("EXTRATO\n05/11 LOJA 10,00 D").type == TransactionType.DEBIT
    assert _um("EXTRATO\n05/11 DEPOSITO 10,00 C").type == TransactionType.CREDIT


def test_fatura_valor_sem_sinal_e_compra():
    tx = _um("FATURA DO CARTAO\n05/11 MERCADO CENTRAL 89,90")
    assert tx.type == TransactionType.DEBIT


def test_extrato_valor_sem_sinal_e_entrada():
    assert _um("EXTRATO\n05/11 DEPOSITO 89,90").type == TransactionType.CREDIT


def test_parcela_e_extraida_e_removida_da_descricao():
    tx = _um("FATURA\n05/11 MERCADO LIVRE 03/10 89,90")
    assert (tx.installment_number, tx.installment_total) == (3, 10)
    assert tx.description == "MERCADO LIVRE"


def test_data_sem_ano_nao_fica_no_futuro():
    # fatura de dezembro lida em janeiro: o ano é o anterior
    tx = _um("EXTRATO\n20/12 LOJA -10,00", hoje=date(2027, 1, 5))
    assert tx.date == date(2026, 12, 20)
    # mês anterior ao atual fica no mesmo ano
    assert _um("EXTRATO\n20/10 LOJA -10,00", hoje=date(2026, 11, 18)).date == date(2026, 10, 20)


def test_data_invalida_e_ignorada():
    assert ParserService.parse_pdf_text("EXTRATO\n31/02 LOJA -10,00", today=HOJE) == []


def test_linhas_sem_lancamento_sao_ignoradas():
    texto = "FATURA\nTotal de compras: R$ 815,50\nVencimento 10/12\nPagina 1"
    assert ParserService.parse_pdf_text(texto, today=HOJE) == []


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("DROGASIL 123", TransactionCategory.HEALTH),
        ("UBER EATS", TransactionCategory.FOOD),
        ("UBER *TRIP", TransactionCategory.TRANSPORT),
        ("CONTA DE GAS", TransactionCategory.HOUSING),
        ("Mercado Livre", TransactionCategory.SERVICES),
        ("Supermercados BH", TransactionCategory.FOOD),
        ("Burger King", TransactionCategory.FOOD),
        ("Loja Desconhecida", TransactionCategory.OTHER),
    ],
)
def test_categorizacao_por_palavra_inteira(texto, esperado):
    assert CategorizationService.categorize(texto, tx_type=TransactionType.DEBIT) == esperado
