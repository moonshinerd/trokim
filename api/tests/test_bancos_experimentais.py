"""Bancos do registro (ADR 0022): detecção por conteúdo, perfis de PDF/OFX e GET /v1/banks."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.bank_pdf_profiles import (
    parse_bank_pdf,
    parse_inter_fatura,
    parse_itau_fatura,
    parse_mercadopago_extrato,
    parse_picpay_extrato,
)
from app.services.bank_registry import (
    BankInfo,
    detect_ofx_bank,
    detect_pdf_bank,
    get_bank,
    register_bank,
    unregister_bank,
)
from app.services.parser_service import ParserService

MP = """EXTRATO DE CONTA
De 01-11-2026 al 30-11-2026
Saldo inicial R$ 100,00
Entradas R$ 50,00
Saidas R$ -30,00
Saldo final R$ 120,00
DETALHE DOS MOVIMENTOS
Data Descrição ID da operação Valor Saldo
05-11-2026
Pix recebido FULANO
DE TAL 123456789012 R$ 50,00 R$ 150,00
10-11-2026
Pagamento Padaria 123456789013 R$ -30,00 R$ 120,00
"""

INTER = """Despesas da fatura
12 de nov. 2026 MERCADO CENTRAL (Parcela 02 de 10) R$ 40,00
13 de nov. 2026 PAGAMENTO ON LINE + R$ 15,00
Total da sua fatura R$ 25,00
"""

ITAU = """itau unibanco
Vencimento: 10/12/2026
lançamentos: compras e saques
03/11 LOJA X 02/05 80,00
05/11 ESTORNO LOJA -20,00
total dos lançamentos atuais 60,00
"""

PICPAY = "PicPay\n02/11/2026 Recarga de celular R$ -20,00\n03/11/2026 Pix recebido R$ 100,00\n"


def test_mercadopago_fecha_com_o_saldo():
    r = parse_mercadopago_extrato(MP, "mp.pdf")
    assert r and len(r.transactions) == 2 and r.reconciled is True
    assert r.transactions[0].description.startswith("Pix recebido")


def test_inter_parcela_credito_e_total():
    r = parse_inter_fatura(INTER, "i.pdf")
    assert r and r.reconciled is True
    compra = r.transactions[0]
    assert (compra.installment_number, compra.installment_total) == (2, 10)
    assert r.transactions[1].type.value == "credit"


def test_itau_ano_do_vencimento_e_total():
    r = parse_itau_fatura(ITAU, "t.pdf")
    assert r and r.reconciled is True and r.transactions[0].installment_total == 5


def test_picpay_sinal():
    r = parse_picpay_extrato(PICPAY, "p.pdf")
    assert r and [t.type.value for t in r.transactions] == ["debit", "credit"]


def test_dispatcher_ignora_texto_desconhecido():
    assert parse_bank_pdf("texto qualquer", "x.pdf") is None
    assert parse_bank_pdf(MP, "mp.pdf").institution == "mercadopago"


def test_detecao_por_conteudo():
    assert detect_ofx_bank("Banco Inter S.A.", set()) == "inter"
    assert detect_ofx_bank("", {"0341"}) == "itau"
    assert detect_pdf_bank("Fatura C6 Bank") == "c6"


def test_ofx_itau_classifica_pix_e_fatura():
    ofx = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20261120<LANGUAGE>POR<FI><ORG>Itau<FID>341</FI></SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>341<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20261101<DTEND>20261120
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261105<TRNAMT>-50.00<FITID>1<MEMO>PIX ENVIADO JOAO</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261106<TRNAMT>-300.00<FITID>2
<MEMO>PAGAMENTO FATURA CARTAO</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    r = ParserService.parse_ofx_detailed(ofx, "itau.ofx")
    assert r.institution == "itau"
    natures = {t.nature.value for t in r.transactions}
    assert natures == {"pix_enviado", "pagamento_fatura"}


def test_banco_falso_registrado_sem_mexer_no_resto():
    register_bank(
        BankInfo("falso", "Banco Falso", "experimental", ("pdf",), pdf_keywords=("bancofalso",))
    )
    try:
        assert detect_pdf_bank("extrato BancoFalso") == "falso"
        names = [b["bank_id"] for b in TestClient(app).get("/v1/banks").json()]
        assert "falso" in names
    finally:
        unregister_bank("falso")
    with pytest.raises(ValueError):
        register_bank(get_bank("nubank"))


def test_endpoint_banks_niveis():
    data = {b["bank_id"]: b["support_level"] for b in TestClient(app).get("/v1/banks").json()}
    assert data["nubank"] == data["bb"] == "validado"
    assert {data[k] for k in ("picpay", "mercadopago", "inter", "c6", "itau")} == {"experimental"}


def test_bordas_pdf_nao_quebram():
    # vazio, só cabeçalho, linha sem valor, data impossível, valor com milhar
    for text in (
        "",
        "EXTRATO DE CONTA\nID da operação",
        "Despesas da fatura\n99 de xyz. 2026 A R$ 1,00",
    ):
        assert parse_bank_pdf(text, "x.pdf") is None
    big = "Despesas da fatura\n01 de dez. 2026 TV R$ 1.234,56\nTotal da sua fatura R$ 1.234,56"
    assert parse_inter_fatura(big, "i.pdf").reconciled is True
    # total diferente da soma: não fecha
    bad = big.replace("Total da sua fatura R$ 1.234,56", "Total da sua fatura R$ 9,00")
    assert parse_inter_fatura(bad, "i.pdf").reconciled is False
    # Itaú sem vencimento: abstém-se em vez de chutar o ano
    assert parse_itau_fatura("lançamentos: compras e saques\n03/11 X 1,00", "t.pdf") is None
    # Itaú: compra de dezembro numa fatura que vence em janeiro cai no ano anterior
    jan = "itau unibanco\nVencimento: 10/01/2027\nlançamentos: compras e saques\n20/12 LOJA 10,00"
    assert parse_itau_fatura(jan, "t.pdf").transactions[0].date.year == 2026


PICPAY_FATURA = """Picpay Card final 1234
Vencimento: 05-01-2026
Transações Nacionais
Data Estabelecimento Valor
20/12 LOJA TESTE PARC 02/03 1.234,56
22/12 PAGAMENTO DE FATURA 500,00
Subtotal 1.234,56
"""


def test_picpay_fatura_parcela_ano_e_pagamento():
    r = parse_bank_pdf(PICPAY_FATURA, "p.pdf")
    assert r and r.kind == "cartao" and len(r.transactions) == 2
    compra, pagto = r.transactions
    assert (compra.installment_number, compra.installment_total) == (2, 3)
    assert compra.amount == 1234.56 and compra.date.year == 2025  # dezembro, vence em janeiro
    assert pagto.type.value == "credit" and pagto.nature.value == "pagamento_fatura"
    # sem vencimento: abstém-se
    assert parse_bank_pdf(PICPAY_FATURA.replace("Vencimento: 05-01-2026", ""), "p.pdf") is None


def test_itau_usa_emissao_quando_nao_ha_vencimento():
    t = "itau unibanco\nEmissão: 28/11/2026\nlançamentos: compras e saques\n03/11 X 5,00"
    assert parse_itau_fatura(t, "t.pdf").transactions[0].date.year == 2026


C6_CSV = (
    "Data de Compra;Nome no Cartão;Final do Cartão;Categoria;Descrição;Parcela;"
    "Valor (em US$);Cotação (em R$);Valor (em R$)\n"
    "05/11/2026;FULANO;1234;Supermercados;MERCADO CENTRAL;Única;0;0;1.234,56\n"
    "10/11/2026;FULANO;1234;Eletrônicos;LOJA TECH;02/05;0;0;200.00\n"
    "12/11/2026;FULANO;1234;Pagamento;PAGAMENTO FATURA;Única;0;0;-1000,00\n"
)


def test_c6_csv_valores_parcela_e_sinal():
    from app.services.bank_csv_profiles import parse_c6_fatura_csv

    r = parse_c6_fatura_csv(C6_CSV.encode(), "Fatura_2026-11-20.csv")
    assert r and r.institution == "c6" and r.kind == "cartao" and len(r.transactions) == 3
    compra, parcela, pagto = r.transactions
    assert compra.amount == 1234.56 and compra.type.value == "debit"
    assert (parcela.installment_number, parcela.installment_total) == (2, 5)
    assert parcela.amount == 200.0  # formato com ponto decimal também
    assert pagto.type.value == "credit" and pagto.nature.value == "pagamento_fatura"
    assert r.meta.acct_id == "c6-1234"


def test_c6_csv_bordas():
    from app.services.bank_csv_profiles import parse_c6_fatura_csv

    assert parse_c6_fatura_csv(b"", "x.csv") is None
    assert parse_c6_fatura_csv(b"a;b;c\n1;2;3", "x.csv") is None  # cabeçalho que não bate
    latin = C6_CSV.encode("latin-1")  # acentos em latin-1
    assert len(parse_c6_fatura_csv(latin, "x.csv").transactions) == 3
    ruim = C6_CSV + "31/02/2026;F;1234;X;DATA IMPOSSIVEL;Única;0;0;5,00\nlinha curta\n"
    assert len(parse_c6_fatura_csv(ruim.encode(), "x.csv").transactions) == 3


def test_upload_csv_c6_pela_api():
    client = TestClient(app)
    r = client.post(
        "/v1/transactions/upload",
        files={"file": ("Fatura_2026-11-20.csv", C6_CSV.encode(), "text/csv")},
        data={"confirmed": "true"},
    )
    assert r.status_code == 200, r.text
    # CSV de outro layout: recusado com mensagem clara, sem quebrar
    r2 = client.post(
        "/v1/transactions/upload",
        files={"file": ("qualquer.csv", b"a;b\n1;2", "text/csv")},
        data={"confirmed": "true"},
    )
    assert r2.status_code in (400, 415, 422)


def test_movimento_entre_contas_proprias_fica_fora_dos_totais():
    from app.domain.models import TransactionNature as N
    from app.domain.models import TransactionType as T
    from app.services.bank_profiles import bank_nature

    assert bank_nature("Recarga PicPay", T.CREDIT, None) == N.INTERNAL_TRANSFER
    assert bank_nature("Recarga de saldo", T.DEBIT, None) == N.INTERNAL_TRANSFER
    assert bank_nature("Transferência entre contas", T.DEBIT, None) == N.INTERNAL_TRANSFER
    # recarga de celular continua sendo compra; Pix para outra pessoa continua sendo Pix
    assert bank_nature("Recarga de celular", T.DEBIT, None) == N.PURCHASE
    assert bank_nature("Pix enviado FULANO", T.DEBIT, None) == N.PIX_OUT
    # mesmo depois de limpar o documento, o texto de pagamento de fatura vence
    assert bank_nature("Pagamento de fatura PicPay Card", T.DEBIT, None) == N.CARD_PAYMENT
