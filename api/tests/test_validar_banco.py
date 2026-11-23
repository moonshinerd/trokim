"""``make validar-banco``: confere arquivo real imprimindo só números agregados."""

from pathlib import Path

from app.services.parser_service import ParserService
from scripts.validar_banco import brl, main

CSV = (
    "Data de Compra;Nome no Cartão;Final do Cartão;Categoria;Descrição;Parcela;"
    "Valor (em US$);Cotação (em R$);Valor (em R$)\n"
    "05/11/2026;MARIA SILVA;1234;X;LOJA SECRETA DA MARIA;Única;0;0;1.234,56\n"
)


def test_saida_agregada_sem_descricao_nem_nome(tmp_path: Path, capsys):
    f = tmp_path / "fatura.csv"
    f.write_text(CSV, encoding="utf-8")
    assert main(["x", str(f)]) == 0
    out = capsys.readouterr().out
    assert "C6 Bank (experimental)" in out and "R$ 1.234,56" in out and "...1234" in out
    for segredo in ("MARIA", "SILVA", "SECRETA", "LOJA"):
        assert segredo not in out


def test_erros_nao_vazam_conteudo(tmp_path: Path, capsys):
    assert main(["x"]) == 2
    assert main(["x", str(tmp_path / "nao.csv")]) == 2
    ruim = tmp_path / "ruim.ofx"
    ruim.write_bytes(b"CONTEUDO PRIVADO \xff\xfe isso nao e ofx")
    assert main(["x", str(ruim)]) == 1
    assert "PRIVADO" not in capsys.readouterr().out
    desconhecido = tmp_path / "x.csv"
    desconhecido.write_text("a;b\n1;2")
    assert main(["x", str(desconhecido)]) == 1


def test_formato_brasileiro():
    assert brl(1234567.5) == "R$ 1.234.567,50" and brl(0) == "R$ 0,00"


def test_ofx_itau_em_latin1_com_acentos():
    ofx = (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nENCODING:USASCII\nCHARSET:1252\n\n"
        "<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20261120"
        "<LANGUAGE>POR<FI><ORG>Itau<FID>341</FI></SONRS></SIGNONMSGSRSV1><BANKMSGSRSV1><STMTTRNRS>"
        "<TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS><STMTRS><CURDEF>BRL<BANKACCTFROM>"
        "<BANKID>341<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST>"
        "<DTSTART>20261101<DTEND>20261120<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261105"
        "<TRNAMT>-42.90<FITID>1<MEMO>PADARIA SÃO JOÃO AÇAÍ</STMTTRN></BANKTRANLIST>"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
    ).encode("latin-1")
    r = ParserService.parse_ofx_detailed(ofx, "itau.ofx")
    assert r.institution == "itau" and len(r.transactions) == 1
    assert "SÃO JOÃO" in r.transactions[0].description.upper()
