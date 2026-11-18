import io

from fastapi import APIRouter, File, HTTPException, UploadFile
from pypdf import PdfReader

from app.domain.models import FinancialSummary, Transaction
from app.services.calculation_service import CalculationService
from app.services.parser_service import ParserService

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Repositório em memória para a sessão local do MVP (alimentado pelo parser)
_LOCAL_TRANSACTIONS: list[Transaction] = []


def get_imported_transactions() -> list[Transaction]:
    """Retorna cópia da lista de lançamentos importados na sessão local."""
    return list(_LOCAL_TRANSACTIONS)


@router.get("", response_model=list[Transaction])
async def list_transactions():
    return _LOCAL_TRANSACTIONS


@router.get("/summary", response_model=FinancialSummary)
async def get_summary():
    return CalculationService.calculate_summary(_LOCAL_TRANSACTIONS)


@router.post("/upload", response_model=dict)
async def upload_statement(file: UploadFile = File(...)):
    filename = file.filename or "arquivo_desconhecido"
    content = await file.read()

    new_txs: list[Transaction] = []
    institution: str | None = None
    kind: str | None = None
    ledger_balance: float | None = None

    if filename.lower().endswith(".ofx"):
        try:
            parsed = ParserService.parse_ofx_detailed(content, filename=filename)
            new_txs = parsed.transactions
            institution, kind, ledger_balance = (
                parsed.institution,
                parsed.kind,
                parsed.ledger_balance,
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Erro ao processar arquivo OFX: {str(e)}"
            ) from e
    elif filename.lower().endswith(".pdf"):
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
    else:
        raise HTTPException(
            status_code=400,
            detail="Formato de arquivo não suportado no MVP. Envie um arquivo .ofx ou .pdf.",
        )

    # Reenviar o mesmo extrato não pode contar os lançamentos duas vezes.
    ParserService.deduplicate(new_txs, known=_LOCAL_TRANSACTIONS)
    _LOCAL_TRANSACTIONS.extend(new_txs)
    summary = CalculationService.calculate_summary(_LOCAL_TRANSACTIONS)

    return {
        "filename": filename,
        "imported_count": len(new_txs),
        "duplicate_count": sum(1 for tx in new_txs if tx.is_duplicate),
        "total_active_transactions": len(_LOCAL_TRANSACTIONS),
        "institution": institution,
        "kind": kind,
        "ledger_balance": ledger_balance,
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
    _LOCAL_TRANSACTIONS.clear()
    return {"message": "Extratos limpos com sucesso."}
