"""Preparação de arquivos em memória e portas internas de leitura.

As portas internas serão adaptadas às interfaces definitivas da #87, sem
acoplar o agente ao motor. Nenhum adaptador real é instalado implicitamente.
"""

import io
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

from app.services.image_quality import MAX_PIXELS

MAX_PAGES = 10
MAX_FILE_BYTES = 20 * 1024 * 1024
_RENDER_LOCK = threading.Lock()


class DocumentReadError(Exception):
    """Erro com código seguro; nunca contém o erro bruto do fornecedor."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class TextReading:
    text: str
    confidence: float
    field_confidences: dict[str, float] | None = None


class DocumentOcr(Protocol):
    async def read(self, image: bytes) -> TextReading: ...


class DocumentVision(Protocol):
    async def extract(self, image: bytes, instructions: str, schema: dict[str, object]) -> str: ...


class VisionSanitizer(Protocol):
    """Deve garantir anonimização de pixels; None bloqueia o envio."""

    def sanitize(self, image: bytes) -> bytes | None: ...


@dataclass
class DocumentPage:
    number: int
    text: str | None
    image: Image.Image | None


def decode_image(content: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG"}:
                raise DocumentReadError("UNSUPPORTED_TYPE")
            if image.width * image.height > MAX_PIXELS:
                raise DocumentReadError("PIXEL_LIMIT")
            return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise DocumentReadError("INVALID_IMAGE") from None


def image_bytes(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def render_pdf_page(content: bytes, index: int) -> Image.Image:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise DocumentReadError("PDF_RENDERER_UNAVAILABLE") from None
    with _RENDER_LOCK:
        try:
            with pdfium.PdfDocument(content) as doc:
                page = doc[index]
                try:
                    width, height = page.get_size()
                    if width * height * 4 > MAX_PIXELS:
                        raise DocumentReadError("PIXEL_LIMIT")
                    bitmap = page.render(scale=2)
                    try:
                        return bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        except DocumentReadError:
            raise
        except Exception:
            raise DocumentReadError("INVALID_PDF") from None


def read_pages(content: bytes, media_type: str) -> Iterator[DocumentPage]:
    if len(content) > MAX_FILE_BYTES:
        raise DocumentReadError("FILE_LIMIT")
    if media_type in {"image/jpeg", "image/png"}:
        yield DocumentPage(1, None, decode_image(content))
        return
    if media_type != "application/pdf":
        raise DocumentReadError("UNSUPPORTED_TYPE")
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise DocumentReadError("PASSWORD_PROTECTED")
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise DocumentReadError("PAGE_LIMIT")
        for index, page in enumerate(reader.pages):
            yield DocumentPage(index + 1, page.extract_text() or "", None)
    except DocumentReadError:
        raise
    except Exception:
        raise DocumentReadError("INVALID_PDF") from None
