import pytest

from app.domain.models import (
    CounterpartyKind,
    TransactionCategory,
    TransactionNature,
    TransactionType,
)
from app.services.calculation_service import CalculationService
from app.services.parser_service import ParserService
from app.services.statement_profiles import decode_ofx, detect_statement, normalize_text
from tests.nubank_samples import (
    EXTRATO_PADRAO,
    FATURA_PADRAO,
    extrato_conta,
    fatura_cartao,
    lancamento,
)

N = TransactionNature


def _por_memo(txs, trecho):
    return next(t for t in txs if trecho.lower() in t.description.lower())


def test_detecta_cartao_e_conta_do_nubank():
    assert detect_statement(decode_ofx(FATURA_PADRAO)).kind == "cartao"
    assert detect_statement(decode_ofx(EXTRATO_PADRAO)).kind == "conta"
    assert detect_statement(decode_ofx(FATURA_PADRAO)).institution == "nubank"


def test_banco_desconhecido_cai_no_parser_generico():
    outro = FATURA_PADRAO.replace(b"NU PAGAMENTOS S.A.", b"BANCO QUALQUER").replace(
        b"<FID>260", b"<FID>999"
    )
    resultado = ParserService.parse_ofx_detailed(outro, "x.ofx")
    assert resultado.institution is None
    assert len(resultado.transactions) == 7
    assert all(t.nature == N.OTHER for t in resultado.transactions)


def test_utf8_declarado_como_cp1252_nao_corrompe_acentos():
    txs = ParserService.parse_ofx(FATURA_PADRAO, "f.ofx")
    descricoes = " ".join(t.description for t in txs)
    assert "crédito" in descricoes
    assert "Ã" not in descricoes


def test_cp1252_real_tambem_e_lido():
    bruto = FATURA_PADRAO.decode("utf-8").replace("Crédito", "Cr\xe9dito").encode("cp1252")
    txs = ParserService.parse_ofx(bruto, "f.ofx")
    assert any("crédito" in t.description for t in txs)


def test_cartao_natureza_parcela_e_estabelecimento():
    txs = ParserService.parse_ofx(FATURA_PADRAO, "f.ofx")
    pagamento = _por_memo(txs, "Pagamento da fatura")
    assert pagamento.nature == N.CARD_PAYMENT
    ml = next(t for t in txs if t.merchant == "Mercado Livre")
    assert (ml.installment_number, ml.installment_total) == (3, 10)
    assert ml.nature == N.PURCHASE
    spotify = next(t for t in txs if t.merchant == "Spotify")
    assert spotify.category == TransactionCategory.LEISURE


def test_drogasil_nao_vira_moradia_por_causa_de_gas():
    txs = ParserService.parse_ofx(FATURA_PADRAO, "f.ofx")
    drogasil = next(t for t in txs if "DROGASIL" in (t.merchant or ""))
    assert drogasil.category == TransactionCategory.HEALTH


def test_estorno_com_mesmo_fitid_da_compra_nao_e_duplicata():
    txs = ParserService.parse_ofx(FATURA_PADRAO, "f.ofx")
    assert not any(t.is_duplicate for t in txs)
    estorno = next(t for t in txs if t.nature == N.REFUND)
    assert estorno.type == TransactionType.CREDIT


def test_totais_do_cartao_ignoram_pagamento_e_abatem_estorno():
    resumo = CalculationService.calculate_summary(ParserService.parse_ofx(FATURA_PADRAO, "f.ofx"))
    # compras: 23,90 + 32,34 + 89,90 + 45,00 + 53,48 = 244,62; estorno de 53,48
    assert resumo.total_expenses == pytest.approx(191.14)
    assert resumo.total_income == 0
    assert resumo.excluded_count == 1  # pagamento da fatura


def test_pix_remove_documento_banco_agencia_e_conta():
    txs = ParserService.parse_ofx(EXTRATO_PADRAO, "e.ofx")
    texto = " ".join(t.description + " " + (t.merchant or "") for t in txs)
    for vazamento in ["•••", "/0001", "Agência", "Conta:", "BANCO X", "123456-7"]:
        assert vazamento not in texto
    empresa = next(t for t in txs if t.merchant == "EMPRESA FICTICIA LTDA.")
    assert empresa.counterparty_kind == CounterpartyKind.COMPANY
    pessoa = next(t for t in txs if t.merchant == "Maria Exemplo da Silva")
    assert pessoa.counterparty_kind == CounterpartyKind.PERSON


def test_conta_naturezas_e_totais_sem_movimentacoes_internas():
    txs = ParserService.parse_ofx(EXTRATO_PADRAO, "e.ofx")
    naturezas = {t.nature for t in txs}
    assert {N.PIX_OUT, N.PIX_IN, N.INVESTMENT_REDEEM, N.CARD_PAYMENT, N.INVESTMENT_APPLY} <= (
        naturezas
    )
    resumo = CalculationService.calculate_summary(txs)
    # fora: resgate, pagamento de fatura e dinheiro guardado
    assert resumo.excluded_count == 3
    assert resumo.total_income == pytest.approx(250.00)
    assert resumo.total_expenses == pytest.approx(38.33 + 18.00 + 60.00)


def test_padaria_com_acento_e_categorizada_como_alimentacao():
    txs = ParserService.parse_ofx(EXTRATO_PADRAO, "e.ofx")
    assert _por_memo(txs, "PADARIA").category == TransactionCategory.FOOD


def test_reenviar_o_mesmo_arquivo_nao_duplica():
    primeira = ParserService.parse_ofx(FATURA_PADRAO, "f.ofx")
    segunda = ParserService.parse_ofx(FATURA_PADRAO, "f.ofx")
    ParserService.deduplicate(segunda, known=primeira)
    assert all(t.is_duplicate for t in segunda)


def test_saldo_do_arquivo_e_informado():
    assert ParserService.parse_ofx_detailed(FATURA_PADRAO, "f.ofx").ledger_balance == -250.00
    assert ParserService.parse_ofx_detailed(EXTRATO_PADRAO, "e.ofx").ledger_balance == 1000.00


def test_arquivo_sem_lancamentos():
    vazio = extrato_conta([])
    resultado = ParserService.parse_ofx_detailed(vazio, "e.ofx")
    assert resultado.transactions == []
    assert resultado.kind == "conta"


def test_memo_vazio_e_valor_zero_nao_quebram():
    arquivo = fatura_cartao(
        [
            lancamento("DEBIT", "20261103", "-0.00", "z1", ""),
            lancamento("DEBIT", "20261103", "-10.00", "z2", "   "),
        ]
    )
    txs = ParserService.parse_ofx(arquivo, "f.ofx")
    assert len(txs) == 2
    assert all(t.description for t in txs)


def test_ofx_invalido_levanta_erro():
    with pytest.raises(Exception):  # noqa: B017,PT011
        ParserService.parse_ofx(b"isto nao e um ofx", "x.ofx")


def test_normalize_text_remove_acento_e_caixa():
    assert normalize_text("  PÃO   Quente ") == "pao quente"
