"""Arquivos OFX 100% fictícios no formato do Nubank (nenhum dado real)."""

CABECALHO_CARTAO = (
    "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\n"
    "CHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
)
CABECALHO_CONTA = CABECALHO_CARTAO.replace("USASCII", "UTF-8").replace("1252", "NONE")


def _fi(gerado: str | None) -> str:
    server = f"<DTSERVER>{gerado}120000[0:GMT]</DTSERVER>" if gerado else ""
    return (
        "<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>"
        f"{server}<LANGUAGE>POR</LANGUAGE>"
        "<FI><ORG>NU PAGAMENTOS S.A.</ORG><FID>260</FID></FI></SONRS></SIGNONMSGSRSV1>"
    )


CARTAO_PF = "11111111-2222-3333-4444-555555555555"
CARTAO_PJ = "99999999-8888-7777-6666-555555555555"
CONTA_PF = "0000000-0"
CONTA_PJ = "1111111-1"


def lancamento(tipo: str, data: str, valor: str, fitid: str, memo: str) -> str:
    return (
        f"<STMTTRN><TRNTYPE>{tipo}</TRNTYPE><DTPOSTED>{data}000000[-3:BRT]</DTPOSTED>"
        f"<TRNAMT>{valor}</TRNAMT><FITID>{fitid}</FITID><MEMO>{memo}</MEMO></STMTTRN>"
    )


def fatura_cartao(
    lancamentos: list[str],
    saldo: str = "-250.00",
    acct: str = CARTAO_PF,
    inicio: str = "20261103",
    fim: str = "20261110",
    gerado: str | None = "20261210",
) -> bytes:
    corpo = (
        _fi(gerado) + "<CREDITCARDMSGSRSV1><CCSTMTTRNRS><TRNUID>1001</TRNUID>"
        "<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><CCSTMTRS><CURDEF>BRL</CURDEF>"
        f"<CCACCTFROM><ACCTID>{acct}</ACCTID></CCACCTFROM>"
        f"<BANKTRANLIST><DTSTART>{inicio}000000[-3:BRT]</DTSTART>"
        f"<DTEND>{fim}000000[-3:BRT]</DTEND>"
        + "".join(lancamentos)
        + "</BANKTRANLIST><LEDGERBAL><BALAMT>"
        + saldo
        + f"</BALAMT><DTASOF>{fim}000000[-3:BRT]</DTASOF></LEDGERBAL>"
        "</CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"
    )
    return (CABECALHO_CARTAO + corpo).encode("utf-8")


def extrato_conta(
    lancamentos: list[str],
    saldo: str = "1000.00",
    acct: str = CONTA_PF,
    inicio: str = "20261001",
    fim: str = "20261031",
    gerado: str | None = "20261210",
) -> bytes:
    corpo = (
        _fi(gerado) + "<BANKMSGSRSV1><STMTTRNRS><TRNUID>1</TRNUID>"
        "<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><STMTRS><CURDEF>BRL</CURDEF>"
        f"<BANKACCTFROM><BANKID>0260</BANKID><BRANCHID>1</BRANCHID><ACCTID>{acct}</ACCTID>"
        "<ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>"
        f"<BANKTRANLIST><DTSTART>{inicio}000000[-3:BRT]</DTSTART>"
        f"<DTEND>{fim}000000[-3:BRT]</DTEND>"
        + "".join(lancamentos)
        + "</BANKTRANLIST><LEDGERBAL><BALAMT>"
        + saldo
        + f"</BALAMT><DTASOF>{fim}000000[-3:BRT]</DTASOF></LEDGERBAL>"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
    )
    return (CABECALHO_CONTA + corpo).encode("utf-8")


FATURA_PADRAO = fatura_cartao(
    [
        lancamento("DEBIT", "20261103", "-23.90", "a1", "EBW*Spotify - NuPay"),
        lancamento("DEBIT", "20261104", "-32.34", "a2", "Pix no Crédito - LOJA EXEMPLO"),
        lancamento("DEBIT", "20261105", "-89.90", "a3", "Mercado Livre - Parcela 3/10"),
        lancamento("DEBIT", "20261106", "-45.00", "a4", "DROGASIL 123"),
        lancamento("DEBIT", "20261107", "-53.48", "a5", "99Food"),
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
