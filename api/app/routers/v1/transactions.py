import io
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pypdf import PdfReader

from app.domain.models import (
    AccountKind,
    AccountOwner,
    FinancialSummary,
    Transaction,
)
from app.services.calculation_service import CalculationService
from app.services.detector_service import detect
from app.services.import_service import ImportService, account_label
from app.services.library_service import LIBRARY
from app.services.parser_service import ParserService
from app.services.pdf_profiles import parse_pdf_statement

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Repositório em memória para a sessão local do MVP (alimentado pelo parser). É a mesma lista
# da biblioteca local, que também guarda contas, arquivos e decisões do usuário.
_LOCAL_TRANSACTIONS: list[Transaction] = LIBRARY.transactions


def get_imported_transactions() -> list[Transaction]:
    """Retorna cópia da lista de lançamentos importados na sessão local."""
    return list(_LOCAL_TRANSACTIONS)


def _filter_by_owner(owner: str) -> list[Transaction]:
    if owner == "todas":
        return list(_LOCAL_TRANSACTIONS)
    allowed = {
        account_id
        for account_id, account in LIBRARY.accounts.items()
        if account.owner is not None and account.owner.value == owner
    }
    # Lançamentos de PDF (sem conta cadastrada) só aparecem em "todas".
    return [tx for tx in _LOCAL_TRANSACTIONS if tx.account_id in allowed]


@router.get("", response_model=list[Transaction])
async def list_transactions():
    return _LOCAL_TRANSACTIONS


@router.get("/summary", response_model=FinancialSummary)
async def get_summary(
    owner: Annotated[Literal["todas", "pessoal", "empresa"], Query()] = "todas",
    view: Annotated[Literal["competencia", "caixa"], Query()] = "competencia",
):
    summary = CalculationService.calculate_summary(_filter_by_owner(owner), view=view, owner=owner)
    for row in summary.by_account:
        account = LIBRARY.accounts.get(str(row["account_id"]))
        row["label"] = account_label(account) if account else str(row["account_id"])
        row["owner"] = account.owner.value if account and account.owner else None
        row["kind"] = account.kind.value if account and account.kind else None
    return summary


def _parse_owner(owner: str | None) -> AccountOwner | None:
    if not owner:
        return None
    try:
        return AccountOwner(owner)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="O dono da conta deve ser 'pessoal' ou 'empresa'."
        ) from exc


def _parse_kind(kind: str | None) -> AccountKind | None:
    if not kind:
        return None
    try:
        return AccountKind(kind)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="O tipo esperado deve ser 'conta' ou 'cartao'."
        ) from exc


@router.post("/inspect", response_model=dict)
async def inspect_statement(
    file: Annotated[UploadFile, File()],
    owner: Annotated[str | None, Form()] = None,
    expect_kind: Annotated[str | None, Form()] = None,
):
    """Analisa o arquivo sem importar: banco, tipo, período, dono provável e avisos."""
    filename = file.filename or "arquivo_desconhecido"
    lower = filename.lower()
    content = await file.read()
    parsed = None
    if lower.endswith(".ofx"):
        try:
            parsed = ParserService.parse_ofx_detailed(content, filename)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Erro ao processar arquivo OFX: {str(e)}"
            ) from e
    elif lower.endswith(".pdf"):
        try:
            parsed = parse_pdf_statement(content, filename)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Erro ao processar arquivo PDF: {str(e)}"
            ) from e
    if parsed is None:
        # PDF sem perfil conhecido (ou outro formato): sem o que detectar.
        return {
            "filename": filename,
            "institution": None,
            "kind": None,
            "warnings": [],
            "has_conflict": False,
            "needs_owner": False,
        }
    return detect(LIBRARY, parsed, filename, _parse_owner(owner), _parse_kind(expect_kind))


@router.post("/upload", response_model=dict)
async def upload_statement(
    file: Annotated[UploadFile, File()],
    owner: Annotated[str | None, Form()] = None,
    expect_kind: Annotated[str | None, Form()] = None,
    confirmed: Annotated[bool, Form()] = False,
):
    filename = file.filename or "arquivo_desconhecido"
    content = await file.read()
    account_owner = _parse_owner(owner)
    expected = _parse_kind(expect_kind)

    lower = filename.lower()
    pdf_profile = None
    if lower.endswith(".pdf"):
        try:
            pdf_profile = parse_pdf_statement(content, filename)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Erro ao processar arquivo PDF: {str(e)}"
            ) from e

    if (lower.endswith(".ofx") or pdf_profile is not None) and not confirmed:
        try:
            parsed = (
                pdf_profile
                if pdf_profile is not None
                else ParserService.parse_ofx_detailed(content, filename)
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Erro ao processar arquivo OFX: {str(e)}"
            ) from e
        inspection = detect(LIBRARY, parsed, filename, account_owner, expected)
        if inspection["has_conflict"]:
            first = next(w for w in inspection["warnings"] if w["severity"] == "conflito")  # type: ignore[attr-defined]
            raise HTTPException(
                status_code=409,
                detail=f"{first['message']} Confirme para importar mesmo assim.",
            )

    if lower.endswith(".ofx") or pdf_profile is not None:
        try:
            if pdf_profile is not None:
                result = ImportService.import_parsed(LIBRARY, pdf_profile, filename, account_owner)
            else:
                result = ImportService.import_ofx(LIBRARY, content, filename, account_owner)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Erro ao processar arquivo OFX: {str(e)}"
            ) from e
        new_txs: list[Transaction] = result["txs"]  # type: ignore[assignment]
        extra = {
            "institution": result["institution"],
            "kind": result["kind"],
            "ledger_balance": result["ledger_balance"],
            "outcome": result["outcome"],
            "delta": result["delta"],
            "reconciled": result["reconciled"],
            "account": {
                **result["account"].model_dump(mode="json"),  # type: ignore[attr-defined]
                "display_label": account_label(result["account"]),  # type: ignore[arg-type]
                "needs_owner": result["account"].needs_owner,  # type: ignore[attr-defined]
            },
            "statement": result["statement"].model_dump(mode="json"),  # type: ignore[attr-defined]
            "auto_transfers": result["auto_transfers"],
            "transfer_suggestions": result["suggestion_count"],
        }
    elif lower.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(content))
            extracted_text = ""
            for page in reader.pages:
                extracted_text += page.extract_text() or ""
            new_txs = ParserService.parse_pdf_text(extracted_text, filename=filename)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Erro ao processar arquivo PDF: {str(e)}"
            ) from e
        # Reenviar o mesmo extrato não pode contar os lançamentos duas vezes.
        ParserService.deduplicate(new_txs, known=_LOCAL_TRANSACTIONS)
        _LOCAL_TRANSACTIONS.extend(new_txs)
        extra = {
            "institution": None,
            "kind": None,
            "ledger_balance": None,
            "outcome": "novo",
            "delta": 0,
            "reconciled": None,
            "account": None,
            "statement": None,
            "auto_transfers": 0,
            "transfer_suggestions": 0,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Formato de arquivo não suportado no MVP. Envie um arquivo .ofx ou .pdf.",
        )

    summary = CalculationService.calculate_summary(_LOCAL_TRANSACTIONS)

    return {
        "filename": filename,
        "imported_count": len(new_txs),
        "duplicate_count": sum(1 for tx in new_txs if tx.is_duplicate),
        "total_active_transactions": len(_LOCAL_TRANSACTIONS),
        **extra,
        "by_nature": {
            nature: sum(1 for tx in new_txs if tx.nature.value == nature and not tx.is_duplicate)
            for nature in sorted({tx.nature.value for tx in new_txs})
        },
        "uncategorized_count": sum(
            1 for tx in new_txs if tx.category.value == "outros" and tx.counts_in_totals
        ),
        "summary": summary.model_dump(),
    }


@router.delete("/clear")
async def clear_transactions():
    LIBRARY.reset()
    return {"message": "Extratos limpos com sucesso."}
