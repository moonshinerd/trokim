import io

import pytest
from reportlab.pdfgen import canvas

from tests.helpers_api import cliente


@pytest.fixture
async def client():
    async with cliente() as client:
        yield client


@pytest.fixture
def reviewed():
    return {
        "kind": "pix_receipt",
        "date": "2026-11-20",
        "amount": "12.50",
        "description": "Padaria Sintética",
    }


@pytest.fixture
def invoice(reviewed):
    return {
        **reviewed,
        "kind": "card_invoice",
        "due_date": "2026-11-30",
        "transactions": [
            {"date": reviewed["date"], "description": name, "amount": "6.25"}
            for name in ("Loja A", "Loja B")
        ],
    }


@pytest.fixture
def receipt_pdf():
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    for n, line in enumerate(
        [
            "Comprovante Pix",
            "Data: 20/11/2026",
            "Valor: R$ 12,50",
            "Favorecido: Padaria Sintética",
        ]
    ):
        pdf.drawString(50, 780 - 20 * n, line)
    pdf.save()
    return output.getvalue()
