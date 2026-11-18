"""Gera arquivos OFX sintéticos no formato do Nubank (cartão e conta, pessoal e Empresas).

Dados 100% fictícios (nomes, documentos e contas inventados), usados em demonstrações, no tutorial
do app e na validação do perfil Nubank. Uso: ``python generate_nubank_datasets.py``.

Cenário (todos com a data de geração em 18/11/2026):

- ``fatura_nubank_aberta_pessoal.ofx``: ciclo 03/11 a 03/12, ainda **aberta**, com parcelamentos.
- ``fatura_nubank_fechada_empresas.ofx``: ciclo 11/10 a 11/11, **fechada**, do cartão Empresas.
- ``NU_<conta>_01OUT2026_31OUT2026.ofx``: extrato pessoal de outubro (nome no padrão do Nubank).
- ``<uuid>-2026-10-01-2026-10-31.ofx``: extrato Empresas de outubro (nome no padrão do Nubank).
- Os dois extratos têm Pix entre as duas contas (o texto traz a conta de destino, como no OFX real).
"""

from pathlib import Path

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


PIX_CLIENTE = (
    "Transferência recebida pelo Pix - CLIENTE EXEMPLO SA - 33.333.333/0001-33 - "
    "BANCO X (0001) Agência: 1 Conta: 1-1"
)
PIX_FORNECEDOR = (
    "Transferência enviada pelo Pix - FORNECEDOR EXEMPLO LTDA - 44.444.444/0001-44 - "
    "BANCO Y (0002) Agência: 2 Conta: 2-2"
)
PIX_P_EMPRESA = (
    "Transferência enviada pelo Pix - EMPRESA FICTICIA LTDA. - 11.111.111/0001-11 - "
    "NU PAGAMENTOS S.A. (0260) Agência: 1 Conta: 1111111-1"
)
PIX_RECEBIDO_PESSOA = (
    "Transferência recebida pelo Pix - Maria Exemplo da Silva - •••.123.456-•• - "
    "NU PAGAMENTOS S.A. (0260) Agência: 1 Conta: 0000000-0"
)
PIX_P_PESSOA = PIX_RECEBIDO_PESSOA.replace("recebida", "enviada")
PIX_RECEBIDO_EMPRESA = PIX_P_EMPRESA.replace("enviada", "recebida")
GERADO = "20261118"


def cenario() -> dict[str, bytes]:
    d = lancamento
    return {
        "fatura_nubank_aberta_pessoal.ofx": fatura_cartao(
            [
                d("DEBIT", "20261103", "-23.90", "a1", "EBW*Spotify - NuPay"),
                d("DEBIT", "20261104", "-99.80", "a2", "Mercado Livre - Parcela 5/6"),
                d("DEBIT", "20261105", "-55.00", "a3", "Loja Exemplo - Parcela 6/9"),
                d("DEBIT", "20261107", "-271.61", "a4", "Eletro Exemplo - Parcela 4/8"),
                d("DEBIT", "20261110", "-45.00", "a5", "DROGASIL 123"),
                d("DEBIT", "20261114", "-32.34", "a6", "Pix no Crédito - LOJA EXEMPLO"),
            ],
            saldo="-527.65",
            acct=CARTAO_PF,
            inicio="20261103",
            fim="20261203",
            gerado=GERADO,
        ),
        "fatura_nubank_fechada_empresas.ofx": fatura_cartao(
            [
                d("DEBIT", "20261019", "-120.00", "b1", "Fornecedor Exemplo - Parcela 1/3"),
                d("DEBIT", "20261025", "-64.90", "b2", "Papelaria Exemplo"),
                d("DEBIT", "20261030", "-80.00", "b3", "Software Exemplo"),
                d("CREDIT", "20261010", "264.90", "b4", "Pagamento recebido"),
            ],
            saldo="0.00",
            acct=CARTAO_PJ,
            inicio="20261011",
            fim="20261111",
            gerado=GERADO,
        ),
        "NU_000000000_01OUT2026_31OUT2026.ofx": extrato_conta(
            [
                d(
                    "CREDIT",
                    "20261001",
                    "2500.00",
                    "p1",
                    PIX_CLIENTE,
                ),
                d("DEBIT", "20261005", "-308.76", "p2", PIX_P_EMPRESA),
                d("CREDIT", "20261008", "295.02", "p3", PIX_RECEBIDO_EMPRESA),
                d("DEBIT", "20261010", "-60.00", "p4", "Compra no débito - PADARIA PÃO QUENTE"),
                d("DEBIT", "20261015", "-250.00", "p5", "Pagamento de fatura"),
            ],
            saldo="2000.00",
            acct=CONTA_PF,
            inicio="20261001",
            fim="20261031",
            gerado=GERADO,
        ),
        "6a20b244-bf06-47fb-9f05-e3735a88483c-2026-10-01-2026-10-31.ofx": extrato_conta(
            [
                d("CREDIT", "20261005", "308.76", "j1", PIX_RECEBIDO_PESSOA),
                d("DEBIT", "20261008", "-295.02", "j2", PIX_P_PESSOA),
                d(
                    "DEBIT",
                    "20261012",
                    "-150.00",
                    "j3",
                    PIX_FORNECEDOR,
                ),
                d("DEBIT", "20261030", "-264.90", "j4", "Pagamento de fatura"),
            ],
            saldo="900.00",
            acct=CONTA_PJ,
            inicio="20261001",
            fim="20261031",
            gerado=GERADO,
        ),
        # Arquivos antigos de demonstração (período fechado), mantidos por compatibilidade.
        "fatura_nubank_sintetica.ofx": FATURA_PADRAO,
        "extrato_nubank_sintetico.ofx": EXTRATO_PADRAO,
    }


def main() -> None:
    destino = Path(__file__).parent
    for nome, conteudo in cenario().items():
        (destino / nome).write_bytes(conteudo)
    print("Arquivos Nubank sintéticos gerados em", destino)


if __name__ == "__main__":
    main()
