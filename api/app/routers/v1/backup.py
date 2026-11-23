"""Backup e restauração da biblioteca do usuário (arquivo ``.trokim`` criptografado)."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.services.backup_service import (
    MAX_COMPRESSED_BYTES,
    BackupError,
    export_backup,
    import_backup,
)
from app.services.library_service import LIBRARY
from app.services.library_store import apply_snapshot, snapshot_from

router = APIRouter(prefix="/backup", tags=["Backup"])


class ExportRequest(BaseModel):
    passphrase: str = Field(
        min_length=8,
        max_length=256,
        description="Senha escolhida pelo usuário. Sem ela o backup não abre; ela não é gravada.",
    )


@router.post("/export", response_class=Response)
def export(request: ExportRequest) -> Response:
    content = export_backup(snapshot_from(LIBRARY), request.passphrase)
    filename = f"trokim-{date.today():%Y%m%d}.trokim"
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def restore(
    file: Annotated[UploadFile, File(description="Arquivo .trokim")],
    passphrase: Annotated[str, Form(min_length=8, max_length=256)],
    mode: Annotated[Literal["substituir", "mesclar"], Form()] = "substituir",
) -> dict[str, object]:
    data = await file.read(MAX_COMPRESSED_BYTES + 1)
    try:
        snapshot = import_backup(data, passphrase)
    except BackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    added = apply_snapshot(LIBRARY, snapshot, merge=mode == "mesclar")
    return {"mode": mode, "added": added, "transactions_total": len(LIBRARY.transactions)}
