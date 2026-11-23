"""Bancos suportados e nível de suporte (ADR 0022)."""

from fastapi import APIRouter

from app.services.bank_registry import list_banks

router = APIRouter(prefix="/banks", tags=["bancos"])


@router.get("")
def get_banks() -> list[dict[str, object]]:
    return [
        {
            "bank_id": b.bank_id,
            "display_name": b.display_name,
            "support_level": b.support_level,
            "formats": list(b.formats),
            "note": b.note,
        }
        for b in list_banks()
    ]
