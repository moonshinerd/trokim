"""Fatura Ourocard (Banco do Brasil) 100% fictícia, no layout do PDF real."""

import io

from reportlab.pdfgen.canvas import Canvas


def pdf_de_linhas(linhas: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = Canvas(buffer, invariant=1)
    y = 800
    for linha in linhas:
        pdf.drawString(30, y, linha)
        y -= 14
        if y < 40:
            pdf.showPage()
            y = 800
    pdf.save()
    return buffer.getvalue()


def fatura_bb(
    lancamentos: list[tuple[str, list[str]]],
    *,
    final: str = "1234",
    fechamento: str = "28/10/2026",
    vencimento: str = "10/11/2026",
    anterior: str = "1.000,00",
    total: str | None = None,
) -> bytes:
    """``lancamentos``: lista de (categoria do BB, linhas ``DD/MM DESCRIÇÃO BR R$ valor``)."""
    linhas = [
        "Olá, Fulano de Tal, esta é sua fatura de outubro",
        "Vencimento",
        vencimento,
        f"OUROCARD FACIL VISA Final {final}",
        "Resumo da fatura",
        f"Fatura fechada em {fechamento}",
        "Fechamento da próxima fatura 28/11/2026",
        "Lançamentos nesta fatura",
        f"Fulano de Tal  (Cartão {final})",
        "Data    Descrição País Valor",
        f"SALDO FATURA ANTERIOR BR R$ {anterior}",
    ]
    for categoria, itens in lancamentos:
        linhas.append(categoria)
        linhas.extend(itens)
    linhas.append(f"Total da Fatura R$ {total or '0,00'}")
    linhas.append("Para dúvidas: www.bb.com.br")
    return pdf_de_linhas(linhas)


PAGAMENTO = (
    "Pagamentos/Créditos",
    ["13/10     PGTO. QR CODE PIX 4700 000000000  200 BR R$ -1.000,00"],
)

FATURA_PADRAO = fatura_bb(
    [
        PAGAMENTO,
        (
            "Restaurantes",
            [
                "14/10     IFD*PIZZARIA EXEMPLO - SAO PAULO BR R$ 50,00",
                "15/10     RESTAURANTE EXEMPLO     BRASILIA BR R$ 80,00",
            ],
        ),
        ("Lazer", ["16/10     CINE EXEMPLO     BRASILIA BR R$ 40,00"]),
        ("Serviços", ["17/10     MP*SERVICO EXEMPLO     SAO PAULO BR R$ 30,00"]),
        ("Compras parceladas", ["18/10     MP*LOJA EXEMPLO PARC 03/10 SAO PAULO BR R$ 100,00"]),
    ],
    total="300,00",
)


# --- extrato da conta corrente (OFX "Money 2000+", codificado em ISO-8859-1) -----------------

CONTA_BB = "70182-3"
AGENCIA_BB = "2895-9"


def lancamento_bb(tipo: str, data: str, valor: str, fitid: str, nome: str, memo: str = "") -> str:
    return (
        "<STMTTRN>"
        f"<TRNTYPE>{tipo}</TRNTYPE><DTPOSTED>{data}000000[-3:BRT]</DTPOSTED>"
        f"<TRNAMT>{valor}</TRNAMT><FITID>{fitid}</FITID><CHECKNUM>{fitid[-9:]}</CHECKNUM>"
        f"<NAME>{nome}</NAME><MEMO>{memo}</MEMO></STMTTRN>"
    )


def extrato_bb(
    lancamentos: list[str],
    *,
    acct: str = CONTA_BB,
    inicio: str = "20260818",
    fim: str = "20261031",
    gerado: str | None = "20261118",
    saldo: str = "662.94",
) -> bytes:
    server = f"<DTSERVER>{gerado}120000[-3:BRT]</DTSERVER>" if gerado else ""
    texto = (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\n"
        "CHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
        "<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>"
        f"{server}<LANGUAGE>POR</LANGUAGE><FI><ORG>Banco do Brasil</ORG><FID>1</FID></FI>"
        "</SONRS></SIGNONMSGSRSV1><BANKMSGSRSV1><STMTTRNRS><TRNUID>1</TRNUID>"
        "<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><STMTRS><CURDEF>BRL</CURDEF>"
        f"<BANKACCTFROM><BANKID>1</BANKID><BRANCHID>{AGENCIA_BB}</BRANCHID><ACCTID>{acct}</ACCTID>"
        "<ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>"
        f"<BANKTRANLIST><DTSTART>{inicio}000000[-3:BRT]</DTSTART>"
        f"<DTEND>{fim}000000[-3:BRT]</DTEND>" + "".join(lancamentos) + "</BANKTRANLIST>"
        f"<LEDGERBAL><BALAMT>{saldo}</BALAMT><DTASOF>{fim}000000[-3:BRT]</DTASOF></LEDGERBAL>"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
    )
    return texto.encode("cp1252")
