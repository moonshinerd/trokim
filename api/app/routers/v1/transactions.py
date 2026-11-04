import io

from fastapi import APIRouter, File, HTTPException, UploadFile
from pypdf import PdfReader

from app.domain.models import FinancialSummary, Transaction
from app.services.calculation_service import CalculationService
from app.services.parser_service import ParserService

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Repositório em memória para a sessão local do MVP (alimentado pelo parser)
_LOCAL_TRANSACTIONS: list[Transaction] = []


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

    if filename.lower().endswith(".ofx"):
        try:
            new_txs = ParserService.parse_ofx(content, filename=filename)
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

    _LOCAL_TRANSACTIONS.extend(new_txs)
    summary = CalculationService.calculate_summary(_LOCAL_TRANSACTIONS)

    return {
        "filename": filename,
        "imported_count": len(new_txs),
        "total_active_transactions": len(_LOCAL_TRANSACTIONS),
        "summary": summary.model_dump(),
    }


@router.delete("/clear")
async def clear_transactions():
    _LOCAL_TRANSACTIONS.clear()
    return {"message": "Extratos limpos com sucesso."}
