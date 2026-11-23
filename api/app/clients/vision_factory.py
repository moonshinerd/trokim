"""Fábricas dos provedores de OCR e de visão configurados (ADR 0021)."""

from app.clients.litellm_vision_provider import LiteLLMVisionProvider
from app.clients.mock_vision import MockOcrProvider, MockVisionProvider
from app.clients.rapidocr_provider import RapidOcrProvider
from app.clients.tesseract_provider import TesseractProvider
from app.core.config import settings
from app.models.vision_provider import OcrProvider, VisionProvider


class RemoteVisionNotAllowedError(RuntimeError):
    """O modelo de visão configurado envia a imagem para fora do aparelho sem consentimento."""


def get_ocr_provider(provider_name: str | None = None) -> OcrProvider:
    selected = (provider_name or settings.OCR_PROVIDER).lower()
    if selected == "rapidocr":
        return RapidOcrProvider()
    if selected == "mock":
        return MockOcrProvider()
    if selected == "tesseract":
        return TesseractProvider()
    raise ValueError(f"OCR_PROVIDER desconhecido: '{selected}' (use rapidocr, tesseract ou mock).")


def get_vision_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    allow_remote: bool | None = None,
) -> VisionProvider | None:
    """Devolve o modelo de visão, ou ``None`` quando está desligado (padrão).

    Um modelo remoto (por exemplo ``openrouter/...``) só é aceito com
    ``VISION_ALLOW_REMOTE=true``: a imagem sairia do aparelho.
    """
    selected = (provider_name or settings.VISION_PROVIDER).lower()
    if selected == "none":
        return None
    if selected == "mock":
        return MockVisionProvider(model=model_name or "mock-vision")
    if selected != "litellm":
        raise ValueError(f"VISION_PROVIDER desconhecido: '{selected}' (use none, litellm ou mock).")
    provider = LiteLLMVisionProvider(model=model_name)
    permitted = settings.VISION_ALLOW_REMOTE if allow_remote is None else allow_remote
    if provider.is_remote and not permitted:
        raise RemoteVisionNotAllowedError(
            f"O modelo '{provider.model}' envia a imagem para fora do aparelho. "
            "Para usá-lo, o usuário precisa consentir (VISION_ALLOW_REMOTE=true)."
        )
    return provider
