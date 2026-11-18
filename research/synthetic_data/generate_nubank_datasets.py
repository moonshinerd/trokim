"""Gera arquivos OFX sintéticos no formato do Nubank (cartão e conta).

Dados 100% fictícios (nomes, documentos e contas inventados), usados em demonstrações,
no tutorial do app e na validação do perfil Nubank. Uso: ``python generate_nubank_datasets.py``.
"""

from pathlib import Path

CABECALHO_CARTAO = (
    "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\n"
    "CHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
)
CABECALHO_CONTA = CABECALHO_CARTAO.replace("USASCII", "UTF-8").replace("1252", "NONE")

_FI = (
    "<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>"
    "<DTSERVER>20261210120000[0:GMT]</DTSERVER><LANGUAGE>POR</LANGUAGE>"
    "<FI><ORG>NU PAGAMENTOS S.A.</ORG><FID>260</FID></FI></SONRS></SIGNONMSGSRSV1>"
)


def lancamento(tipo: str, data: str, valor: str, fitid: str, memo: str) -> str:
    return (
        f"<STMTTRN><TRNTYPE>{tipo}</TRNTYPE><DTPOSTED>{data}000000[-3:BRT]</DTPOSTED>"
        f"<TRNAMT>{valor}</TRNAMT><FITID>{fitid}</FITID><MEMO>{memo}</MEMO></STMTTRN>"
    )


def fatura_cartao(lancamentos: list[str], saldo: str = "-250.00") -> bytes:
    corpo = (
        _FI + "<CREDITCARDMSGSRSV1><CCSTMTTRNRS><TRNUID>1001</TRNUID>"
        "<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><CCSTMTRS><CURDEF>BRL</CURDEF>"
        "<CCACCTFROM><ACCTID>11111111-2222-3333-4444-555555555555</ACCTID></CCACCTFROM>"
        "<BANKTRANLIST><DTSTART>20261103000000[-3:BRT]</DTSTART>"
        "<DTEND>20261110000000[-3:BRT]</DTEND>"
        + "".join(lancamentos)
        + "</BANKTRANLIST><LEDGERBAL><BALAMT>"
        + saldo
        + "</BALAMT><DTASOF>20261110000000[-3:BRT]</DTASOF></LEDGERBAL>"
        "</CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"
    )
    return (CABECALHO_CARTAO + corpo).encode("utf-8")


def extrato_conta(lancamentos: list[str], saldo: str = "1000.00") -> bytes:
    corpo = (
        _FI + "<BANKMSGSRSV1><STMTTRNRS><TRNUID>1</TRNUID>"
        "<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><STMTRS><CURDEF>BRL</CURDEF>"
        "<BANKACCTFROM><BANKID>0260</BANKID><BRANCHID>1</BRANCHID><ACCTID>0000000-0</ACCTID>"
        "<ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>"
        "<BANKTRANLIST><DTSTART>20261001000000[-3:BRT]</DTSTART>"
        "<DTEND>20261031000000[-3:BRT]</DTEND>"
        + "".join(lancamentos)
        + "</BANKTRANLIST><LEDGERBAL><BALAMT>"
        + saldo
        + "</BALAMT><DTASOF>20261031000000[-3:BRT]</DTASOF></LEDGERBAL>"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
    )
    return (CABECALHO_CONTA + corpo).encode("utf-8")


FATURA_PADRAO = fatura_cartao(
    [
        lancamento("DEBIT", "20261103", "-23.90", "a1", "EBW*Spotify - NuPay"),
        lancamento("DEBIT", "20261104", "-32.34", "a2", "Pix no Crédito - LOJA EXEMPLO"),
        lancamento("DEBIT", "20261105", "-89.90", "a3", "Mercado Livre - Parcela 3/10"),
        lancamento("DEBIT", "20261106", "-45.00", "a4", "DROGASIL 123"),
        lancamento("DEBIT", "20261107", "-53.48", "a5", "99Food - Pedido"),
        lancamento("CREDIT", "20261108", "53.48", "a5", "99Food - Estorno"),
        lancamento("CREDIT", "20261109", "500.00", "a6", "Pagamento recebido"),
    ]
)

EXTRATO_PADRAO = extrato_conta(
    [
        lancamento(
            "DEBIT",
            "20261002",
            "-38.33",
            "b1",
            "Transferência enviada pelo Pix - EMPRESA FICTICIA LTDA. - 11.111.111/0001-11 - "
            "BANCO X (0001) Agência: 1 Conta: 123456-7",
        ),
        lancamento(
            "DEBIT",
            "20261003",
            "-18.00",
            "b2",
            "Transferência enviada pelo Pix - Maria Exemplo da Silva - •••.123.456-•• - "
            "BANCO Y (0002) Agência: 2 Conta: 765432-1",
        ),
        lancamento(
            "CREDIT",
            "20261004",
            "250.00",
            "b3",
            "Transferência recebida pelo Pix - João Exemplo - •••.654.321-•• - "
            "BANCO Z (0003) Agência: 3 Conta: 111222-3",
        ),
        lancamento("CREDIT", "20261005", "644.61", "b4", "Resgate RDB"),
        lancamento("DEBIT", "20261006", "-300.00", "b5", "Pagamento de fatura"),
        lancamento("DEBIT", "20261007", "-60.00", "b6", "Compra no débito - PADARIA PÃO QUENTE"),
        lancamento("DEBIT", "20261008", "-200.00", "b7", "Dinheiro guardado com resgate planejado"),
    ]
)


def main() -> None:
    destino = Path(__file__).parent
    (destino / "fatura_nubank_sintetica.ofx").write_bytes(FATURA_PADRAO)
    (destino / "extrato_nubank_sintetico.ofx").write_bytes(EXTRATO_PADRAO)
    print("Arquivos Nubank sintéticos gerados em", destino)


if __name__ == "__main__":
    main()
