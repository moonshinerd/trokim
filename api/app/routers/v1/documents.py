"""Documentos por foto ou PDF: extrair, revisar e confirmar (#96). Sem regra de negócio aqui."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.request_lifecycle import run_while_connected
from app.domain.documents import (
    DocumentConfirmRequest,
    DocumentConfirmResponse,
    DocumentExtractResponse,
)
from app.services.agents.document_pipeline import DocumentFailure, DocumentPipeline
from app.services.document_confirmation import ConfirmationBlocked, confirm_document
from app.services.document_factory import get_document_agent
from app.services.document_reading import MAX_FILE_BYTES
from app.services.library_service import LIBRARY

router = APIRouter(prefix="/documents", tags=["Documentos"])

# Tipo pelo conteúdo, nunca pelo cabeçalho que o cliente mandou.
_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
)
# Código seguro da falha -> (status HTTP, mensagem em pt-BR).
_FAILURES = {
    "OCR_UNAVAILABLE": (503, "A leitura de imagens não está disponível neste computador."),
    "PDF_RENDERER_UNAVAILABLE": (503, "A leitura de PDF escaneado não está disponível."),
    "FILE_LIMIT": (413, "O arquivo é grande demais."),
    "PIXEL_LIMIT": (413, "A imagem tem resolução alta demais."),
    "PAGE_LIMIT": (413, "O PDF tem páginas demais."),
    "UNSUPPORTED_TYPE": (415, "Envie uma foto JPEG ou PNG, ou um PDF."),
    "INVALID_IMAGE": (422, "Não consegui abrir a imagem."),
    "INVALID_PDF": (422, "Não consegui abrir o PDF."),
    "PASSWORD_PROTECTED": (422, "O PDF tem senha; remova a senha e envie de novo."),
    "MIXED_DOCUMENT_KINDS": (422, "O arquivo mistura documentos diferentes; envie um de cada vez."),
}


def get_document_pipeline() -> DocumentPipeline:
    return DocumentPipeline(get_document_agent())


def _media_type(content: bytes) -> str | None:
    return next((kind for magic, kind in _MAGIC if content.startswith(magic)), None)


async def _read_limited(upload: UploadFile) -> bytes:
    """Lê o arquivo parando no limite, para não carregar na memória um envio gigante."""
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "FILE_LIMIT", "message": _FAILURES["FILE_LIMIT"][1]},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/extract",
    response_model=DocumentExtractResponse,
    summary="Lê um comprovante, boleto ou fatura (foto ou PDF) e valida o resultado",
    responses={413: {}, 415: {}, 422: {}, 503: {}},
)
async def extract_document(
    file: Annotated[UploadFile, File()],
    connection: Request,
    pipeline: Annotated[DocumentPipeline, Depends(get_document_pipeline)],
) -> DocumentExtractResponse:
    try:
        content = await _read_limited(file)
    finally:
        await file.close()  # apaga o arquivo temporário que o multipart pode ter criado
    media_type = _media_type(content)
    if media_type is None:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_TYPE", "message": _FAILURES["UNSUPPORTED_TYPE"][1]},
        )
    try:
        return await run_while_connected(connection, pipeline.run(content, media_type, LIBRARY))
    except DocumentFailure as failure:
        status, message = _FAILURES.get(
            failure.code, (500, "Não foi possível processar o documento.")
        )
        raise HTTPException(
            status_code=status, detail={"code": failure.code, "message": message}
        ) from None


@router.post(
    "/confirm",
    response_model=DocumentConfirmResponse,
    summary="Cria o lançamento a partir dos campos que o usuário revisou",
    responses={422: {}},
)
def confirm(request: DocumentConfirmRequest) -> DocumentConfirmResponse:
    try:
        return confirm_document(LIBRARY, request)
    except ConfirmationBlocked as blocked:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CONFIRMATION_BLOCKED",
                "message": "O validador bloqueou este lançamento; corrija os campos.",
                "issues": [i.model_dump(mode="json") for i in blocked.issues],
            },
        ) from None
