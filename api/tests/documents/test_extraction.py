from datetime import date

from app.domain.models import Transaction, TransactionType
from app.services.library_service import LIBRARY


async def test_extracao_e_confirmacao_concordam_sobre_duplicata_sem_conta(
    client, reviewed, receipt_pdf
):
    LIBRARY.transactions.append(
        Transaction(
            account_id="banco:1",
            date=date(2026, 11, 20),
            amount=12.5,
            description=reviewed["description"],
            type=TransactionType.DEBIT,
        )
    )
    extracted = await client.post(
        "/v1/documents/extract", files={"file": ("sintetico.pdf", receipt_pdf)}
    )
    assert extracted.status_code == 200
    assert extracted.json()["can_confirm"] is False
    assert "POSSIBLE_DUPLICATE" in [
        issue["code"] for issue in extracted.json()["validation_issues"]
    ]
    confirmed = await client.post("/v1/documents/confirm", json=reviewed)
    assert confirmed.status_code == 422
    assert len(LIBRARY.transactions) == 1
