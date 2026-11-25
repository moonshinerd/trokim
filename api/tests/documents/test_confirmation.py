from datetime import date

import pytest

from app.domain.models import (
    Account,
    AccountKind,
    Transaction,
    TransactionCategory,
    TransactionNature,
    TransactionOrigin,
    TransactionType,
)
from app.services.categorization_service import merchant_key
from app.services.library_service import LIBRARY


@pytest.mark.parametrize("account_id", [None, "banco:1"])
async def test_duplicata_importada_bloqueia_confirmacao(client, reviewed, account_id):
    LIBRARY.accounts["banco:1"] = Account(id="banco:1", acct_id="1")
    LIBRARY.transactions.append(
        Transaction(
            account_id="banco:1",
            date=date(2026, 11, 20),
            description=reviewed["description"],
            amount=12.5,
            type=TransactionType.DEBIT,
        )
    )
    response = await client.post(
        "/v1/documents/confirm", json={**reviewed, "account_id": account_id}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["issues"][0]["code"] == "POSSIBLE_DUPLICATE"
    assert len(LIBRARY.transactions) == len(LIBRARY.accounts) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"due_date": "2026-11-01"},
        {"kind": "boleto"},
    ],
)
async def test_reenvio_revalida_campos_antes_de_retornar_repetido(client, reviewed, changes):
    assert (await client.post("/v1/documents/confirm", json=reviewed)).status_code == 200
    response = await client.post("/v1/documents/confirm", json={**reviewed, **changes})
    assert response.status_code == 422
    assert len(LIBRARY.transactions) == 1


async def test_fatura_ja_conciliada_e_bloqueada_pelo_total(client, invoice):
    LIBRARY.transactions.append(
        Transaction(
            account_id="banco:1",
            date=date(2026, 11, 20),
            description="Pagamento de fatura",
            amount=12.5,
            type=TransactionType.DEBIT,
            nature=TransactionNature.CARD_PAYMENT,
        )
    )
    response = await client.post("/v1/documents/confirm", json=invoice)
    assert response.status_code == 422
    assert "ALREADY_RECONCILED" in [i["code"] for i in response.json()["detail"]["issues"]]
    assert len(LIBRARY.transactions) == 1
    assert not LIBRARY.accounts


@pytest.mark.parametrize("account_id", [None, "cartao:1"])
async def test_fatura_conta_em_competencia_e_fica_fora_do_caixa(client, invoice, account_id):
    if account_id:
        LIBRARY.accounts[account_id] = Account(id=account_id, acct_id="1", kind=AccountKind.CARD)
    response = await client.post(
        "/v1/documents/confirm", json={**invoice, "account_id": account_id}
    )
    assert response.status_code == 200
    assert (await client.get("/v1/transactions/summary?view=caixa")).json()["total_expenses"] == 0
    assert (await client.get("/v1/transactions/summary")).json()["total_expenses"] == 12.5
    assert all(
        tx.source_kind == "cartao" and tx.origin == TransactionOrigin.DOCUMENT
        for tx in LIBRARY.transactions
    )
    assert LIBRARY.accounts[response.json()["account_id"]].kind == AccountKind.CARD


async def test_pix_recebe_categoria_aprendida_e_respeita_categoria_explicita(client, reviewed):
    LIBRARY.category_rules[merchant_key(reviewed["description"])] = TransactionCategory.LEISURE
    response = await client.post("/v1/documents/confirm", json=reviewed)
    assert response.json()["category"] == "lazer"
    response = await client.post(
        "/v1/documents/confirm", json={**reviewed, "date": "2026-11-19", "category": "saude"}
    )
    assert response.json()["category"] == "saude"
    assert LIBRARY.transactions[0].merchant == reviewed["description"]


async def test_fatura_parcialmente_reenviada_adiciona_apenas_linha_nova(client, invoice):
    first = (await client.post("/v1/documents/confirm", json=invoice)).json()
    invoice["amount"] = "18.75"
    invoice["transactions"].append(
        {"date": invoice["date"], "description": "Loja C", "amount": "6.25"}
    )
    response = await client.post("/v1/documents/confirm", json=invoice)
    assert response.status_code == 200
    assert response.json()["outcome"] == "criado"
    assert response.json()["uids"][:2] == first["uids"]
    assert len(LIBRARY.transactions) == 3
    again = await client.post("/v1/documents/confirm", json=invoice)
    assert again.json()["outcome"] == "repetido"
    assert len(LIBRARY.transactions) == 3


async def test_linha_invalida_nao_deixa_confirmacao_parcial(client, invoice):
    invoice["transactions"][-1]["date"] = "2099-01-01"
    response = await client.post("/v1/documents/confirm", json=invoice)
    assert response.status_code == 422
    assert not LIBRARY.accounts
    assert not LIBRARY.transactions


async def test_linhas_identicas_sao_bloqueadas_sem_alterar_biblioteca(client, invoice):
    invoice["transactions"][1] = dict(invoice["transactions"][0])
    response = await client.post("/v1/documents/confirm", json=invoice)
    assert response.status_code == 422
    assert not LIBRARY.accounts
    assert not LIBRARY.transactions
