"""Contas, arquivos importados, parcelamentos e transferências entre contas próprias."""

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.models import Account, AccountOwner, Statement
from app.services.import_service import ImportService, account_label
from app.services.installment_service import InstallmentService
from app.services.library_service import LIBRARY
from app.services.statement_service import coverage
from app.services.transfer_service import TransferService

router = APIRouter(tags=["Contas e arquivos"])


def account_view(account: Account) -> dict[str, object]:
    return {
        **account.model_dump(mode="json"),
        "display_label": account_label(account),
        "needs_owner": account.needs_owner,
    }


class AccountPatch(BaseModel):
    owner: AccountOwner | None = None
    label: str | None = None


@router.get("/accounts")
async def list_accounts() -> list[dict[str, object]]:
    return [account_view(a) for a in LIBRARY.accounts.values()]


@router.patch("/accounts/{account_id:path}")
async def patch_account(account_id: str, body: AccountPatch) -> dict[str, object]:
    account = LIBRARY.accounts.get(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    if body.owner is not None:
        account.owner = body.owner
    if body.label is not None:
        label = body.label.strip()
        account.label = label[:60] or None
    return account_view(account)


class StatementPatch(BaseModel):
    closed: bool | None = None
    period_start: date | None = None
    period_end: date | None = None


@router.get("/statements")
async def list_statements() -> dict[str, object]:
    statements = list(LIBRARY.statements.values())
    return {
        "statements": [s.model_dump(mode="json") for s in statements],
        "coverage": {
            account_id: {
                **{k: (v.isoformat() if isinstance(v, date) else v) for k, v in info.items()},
                "label": account_label(LIBRARY.accounts[account_id])
                if account_id in LIBRARY.accounts
                else account_id,
            }
            for account_id, info in coverage(statements).items()
        },
    }


@router.patch("/statements/{statement_id}", response_model=Statement)
async def patch_statement(statement_id: str, body: StatementPatch) -> Statement:
    statement = LIBRARY.statements.get(statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    try:
        return ImportService.confirm_statement(
            LIBRARY,
            statement,
            closed=body.closed,
            period_start=body.period_start,
            period_end=body.period_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/installments")
async def get_installments() -> dict[str, object]:
    data = InstallmentService.build(LIBRARY.transactions)
    for plan in data["plans"]:  # type: ignore[attr-defined]
        account = LIBRARY.accounts.get(str(plan["account_id"]))
        plan["account_label"] = account_label(account) if account else str(plan["account_id"])
    return data


class TransferBody(BaseModel):
    debit_uid: str
    credit_uid: str


class UndoBody(BaseModel):
    id: str


def _with_labels(items: list[dict[str, object]]) -> list[dict[str, object]]:
    for item in items:
        for src, dst in (("from_account", "from_label"), ("to_account", "to_label")):
            account = LIBRARY.accounts.get(str(item[src]))
            item[dst] = account_label(account) if account else str(item[src])
    return items


@router.get("/transfers/suggestions")
async def transfer_suggestions() -> list[dict[str, object]]:
    return _with_labels(TransferService.suggestions(LIBRARY))


@router.get("/transfers")
async def confirmed_transfers() -> list[dict[str, object]]:
    items = TransferService.confirmed_list(LIBRARY) + TransferService.automatic_list(LIBRARY)
    return _with_labels(items)


class UnmarkBody(BaseModel):
    uid: str


@router.post("/transfers/unmark")
async def unmark_transfer(body: UnmarkBody) -> dict[str, int]:
    try:
        return {"auto_unmarked": TransferService.unmark(LIBRARY, body.uid)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/transfers/confirm")
async def confirm_transfer(body: TransferBody) -> dict[str, object]:
    try:
        return TransferService.confirm(LIBRARY, body.debit_uid, body.credit_uid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/transfers/reject")
async def reject_transfer(body: TransferBody) -> dict[str, str]:
    return {"id": TransferService.reject(LIBRARY, body.debit_uid, body.credit_uid)}


@router.post("/transfers/undo")
async def undo_transfer(body: UndoBody) -> dict[str, int]:
    try:
        return {"auto_unmarked": TransferService.undo(LIBRARY, body.id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
