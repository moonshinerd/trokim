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
