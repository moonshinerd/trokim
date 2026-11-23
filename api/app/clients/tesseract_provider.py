"""OCR local com o Tesseract (binário do sistema). Nada sai da máquina (ADR 0021).

Alternativa ao RapidOCR quando o Tesseract já está instalado (``apt install tesseract-ocr
tesseract-ocr-por`` ou ``brew install tesseract tesseract-lang``). O binário é chamado direto, sem
biblioteca Python intermediária; a saída TSV traz palavra, confiança (0 a 100) e caixa. O texto
lido nunca vai para log.
"""

import asyncio
import shutil

from app.clients.rapidocr_provider import OcrUnavailableError
from app.core.config import settings
from app.models.vision_provider import OcrResult, OcrWord

_TIMEOUT_SECONDS = 60.0


def parse_tsv(tsv: str) -> list[OcrWord]:
    """Palavras (nível 5) da saída ``tesseract ... tsv``. Linhas sem texto ou sem confiança saem."""
    words: list[OcrWord] = []
    for line in tsv.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) < 12 or cols[0] != "5":
            continue
        text = cols[11].strip()
        try:
            conf = float(cols[10])
            left, top, width, height = (int(cols[i]) for i in (6, 7, 8, 9))
        except ValueError:
            continue
        if not text or conf < 0:
            continue
        words.append(
            OcrWord(
                text=text,
                confidence=max(0.0, min(1.0, conf / 100)),
                box=(left, top, left + width, top + height),
            )
        )
    return words


class TesseractProvider:
    name: str = "tesseract"

    def __init__(self, binary: str | None = None, lang: str | None = None) -> None:
        self._binary = binary or shutil.which("tesseract")
        self._lang = lang or settings.TESSERACT_LANG

    async def read(self, image: bytes) -> OcrResult:
        if not self._binary:
            raise OcrUnavailableError(
                "Tesseract não encontrado: instale o programa (tesseract-ocr e o idioma por)."
            )
        proc = await asyncio.create_subprocess_exec(
            self._binary,
            "stdin",
            "stdout",
            "-l",
            self._lang,
            "--psm",
            "6",
            "tsv",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, _err = await asyncio.wait_for(proc.communicate(image), _TIMEOUT_SECONDS)
        except TimeoutError as exc:
            proc.kill()
            raise OcrUnavailableError("Tesseract demorou demais para ler a imagem.") from exc
        if proc.returncode != 0:
            # A mensagem de erro do programa não é repassada: pode conter trechos da imagem.
            raise OcrUnavailableError(f"Tesseract falhou (código {proc.returncode}).")
        return OcrResult(words=parse_tsv(out.decode("utf-8", errors="replace")), engine=self.name)
