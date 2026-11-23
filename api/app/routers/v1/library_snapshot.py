"""Retrato da biblioteca para o app guardar no aparelho (ADR 0025).

O aparelho é a fonte da verdade: ao abrir, o app envia o retrato que guarda (``PUT``), e depois
de cada alteração o lê de volta (``GET``) para gravá-lo cifrado. A API só o mantém em memória.
Este retrato inclui campos privados, então só deve ser servido a uma API do próprio usuário.
"""

from fastapi import APIRouter

from app.domain.snapshot import LibrarySnapshot
from app.services.library_service import LIBRARY
from app.services.library_store import apply_snapshot, snapshot_from

router = APIRouter(prefix="/library", tags=["Biblioteca no aparelho"])


@router.get("/snapshot", response_model=LibrarySnapshot)
def read_snapshot() -> LibrarySnapshot:
    return snapshot_from(LIBRARY)


@router.put("/snapshot")
def replace_snapshot(snapshot: LibrarySnapshot) -> dict[str, object]:
    added = apply_snapshot(LIBRARY, snapshot)
    return {"added": added, "transactions_total": len(LIBRARY.transactions)}
