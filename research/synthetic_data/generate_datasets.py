"""Gerador de dados sintéticos para testes e validação empírica do Trokim.

Conformidade com LGPD (ADR 0005): Elimina qualquer necessidade de dados reais de usuários.
"""

from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

SAMPLE_OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20261101120000[-03:EST]
<LANGUAGE>POR
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1001
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>0000
<ACCTID>TESTE-SINTETICO-0001
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20261101
<DTEND>20261105
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261101
<TRNAMT>5000.00
<FITID>TX0001
<MEMO>PIX RECEBIDO EMPRESA FICTICIA
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20261102
<TRNAMT>-650.50
<FITID>TX0002
<MEMO>SUPERMERCADO FICTICIO
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20261103
<TRNAMT>-1500.00
<FITID>TX0003
<MEMO>ALUGUEL FICTICIO
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>2849.50
<DTASOF>20261105
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


def generate_synthetic_samples(output_dir: str | None = None) -> None:
    if output_dir:
        path = Path(output_dir)
    else:
        path = Path(__file__).resolve().parent
    path.mkdir(parents=True, exist_ok=True)

    ofx_file = path / "extrato_sintetico_novembro.ofx"
    ofx_file.write_text(SAMPLE_OFX, encoding="utf-8")
    pdf = Canvas(str(path / "fatura_sintetica_novembro.pdf"), invariant=1)
    pdf.setTitle("Fatura fictícia - somente testes")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, 790, "TROKIM | FATURA SINTÉTICA")
    pdf.setFont("Helvetica", 11)
    lines = [
        "Somente testes. Sem titular, CPF ou cartão reais.",
        "Competência: novembro/2026 | Moeda: BRL",
        "02/11/2026 SUPERMERCADO FICTICIO -650,50",
        "03/11/2026 LIVRARIA FICTICIA -120,00",
        "04/11/2026 TRANSPORTE FICTICIO -45,00",
        "Total de compras: R$ 815,50",
    ]
    for index, line in enumerate(lines):
        pdf.drawString(50, 745 - index * 35, line)
    pdf.save()
    print(f"Extrato OFX sintético gerado com sucesso em: {ofx_file}")


if __name__ == "__main__":
    generate_synthetic_samples()
