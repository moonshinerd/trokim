"""Construção do agente com as portas configuráveis da ADR 0021."""

from app.clients.vision_factory import get_ocr_provider, get_vision_provider
from app.core.config import settings
from app.services.agents.document import DocumentAgent
from app.services.document_reading import VisionSanitizer


def get_document_agent(sanitizer: VisionSanitizer | None = None) -> DocumentAgent:
    return DocumentAgent(
        ocr=get_ocr_provider(),
        vision=get_vision_provider(),
        sanitizer=sanitizer,
        timeout=settings.VISION_TIMEOUT,
    )
