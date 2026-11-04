from app.services.parser_service import ParserService


def test_parse_pdf_text_synthetic():
    sample_text = """
    EXTRATO BANCÁRIO SINTÉTICO - TESTE LGPD
    01/11/2026 PIX RECEBIDO EMPRESA XYZ  R$ 5000,00
    03/11/2026 SUPERMERCADO SAO PAULO  -R$ 342,80
    04/11/2026 UBER VIAGEM URBANA  -R$ 28,50
    04/11/2026 UBER VIAGEM URBANA  -R$ 28,50
    """
    txs = ParserService.parse_pdf_text(sample_text, filename="teste_extrato.pdf")

    assert len(txs) == 4
    # A quarta transação deve estar marcada como duplicada
    assert txs[0].amount == 5000.00
    assert txs[0].category.value == "renda"
    assert txs[1].category.value == "alimentacao"
    assert txs[2].category.value == "transporte"
    assert txs[3].is_duplicate is True
