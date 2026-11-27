"""Construção do agente com as portas configuráveis da ADR 0021."""

from typing import Literal

from app.clients.vision_factory import get_ocr_provider, get_vision_provider
from app.core.config import settings
from app.services.agents.document import DocumentAgent
from app.services.document_reading import VisionSanitizer
from app.services.vision_sanitizer import OcrMaskingSanitizer

ReadingEngine = Literal["ocr", "vision"]


class VisionUnavailableError(RuntimeError):
    """O app pediu leitura com visão, mas nenhum modelo de visão está configurado."""


class RemoteConsentRequiredError(RuntimeError):
    """O modelo de visão configurado é remoto e o usuário não consentiu nesta requisição."""


def describe_engines() -> dict[str, object]:
    """Motores disponíveis para o app escolher: OCR local sempre; visão só se configurada."""
    vision = get_vision_provider(allow_remote=True)
    return {
        "ocr": settings.OCR_PROVIDER,
        "vision": None
        if vision is None
        else {"model": vision.model, "remote": bool(vision.is_remote)},
    }


def get_document_agent(
    sanitizer: VisionSanitizer | None = None,
    engine: ReadingEngine | None = None,
    allow_remote: bool = False,
) -> DocumentAgent:
    """Sem ``engine`` (uso interno e testes), segue a configuração do servidor.

    Com ``engine="ocr"``, a visão fica desligada. Com ``engine="vision"``, a visão configurada
    entra como complemento do OCR, com as caixas sensíveis tarjadas; um modelo remoto exige
    ``allow_remote`` (consentimento do usuário nesta requisição).
    """
    if engine is None:
        return DocumentAgent(
            ocr=get_ocr_provider(),
            vision=get_vision_provider(),
            sanitizer=sanitizer,
            timeout=settings.VISION_TIMEOUT,
        )
    vision = None
    if engine == "vision":
        vision = get_vision_provider(allow_remote=True)
        if vision is None:
            raise VisionUnavailableError("Nenhum modelo de visão configurado.")
        if vision.is_remote and not allow_remote:
            raise RemoteConsentRequiredError(f"O modelo '{vision.model}' é remoto.")
    return DocumentAgent(
        ocr=get_ocr_provider(),
        vision=vision,
        sanitizer=sanitizer or OcrMaskingSanitizer(),
        timeout=settings.VISION_TIMEOUT,
        allow_remote=allow_remote,
    )
