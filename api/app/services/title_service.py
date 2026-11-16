"""Nomeia conversas com o LLM configurado, com título determinístico de reserva."""

import asyncio
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.clients.llm_factory import get_llm_provider
from app.core.config import settings
from app.models.llm_provider import LLMProvider

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "prompt_titulo_v1.txt"
MAX_WORDS = 6
# Palavras que não podem terminar um título (o corte de tokens costuma deixá-las soltas).
DANGLING = {
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "e",
    "o",
    "a",
    "um",
    "uma",
    "para",
    "por",
    "com",
    "r$",
    "como",
    "que",
    "ou",
}
MAX_CHARS = 48
DEFAULT_TITLE = "Nova conversa"


class TitleResult(BaseModel):
    title: str
    source: Literal["llm", "fallback"]
    model: str | None = None


def sanitize_title(raw: str) -> str:
    """Normaliza a saída do modelo: uma linha, sem aspas/markdown, até 6 palavras."""
    first_line = next((ln for ln in raw.strip().splitlines() if ln.strip()), "")
    text = re.sub(r"^\s*(t[ií]tulo\s*[:\-–]\s*)", "", first_line, flags=re.IGNORECASE)
    text = re.sub(r"[*_`#>\"“”‘’']", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,:;!?-–—")
    words = text.split()[:MAX_WORDS]
    while len(words) > 1 and words[-1].lower().strip(".,:;") in DANGLING:
        words.pop()
    text = " ".join(words)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0]
    return text[:1].upper() + text[1:] if text else ""


def fallback_title(message: str) -> str:
    """Título determinístico: as primeiras palavras da pergunta, sem pontuação final."""
    clean = re.sub(r"\s+", " ", message).strip()
    text = sanitize_title(clean)
    return text or DEFAULT_TITLE


class TitleService:
    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        timeout: float | None = None,
    ) -> None:
        # Modelo próprio e leve para títulos, se configurado; senão o modelo principal.
        self.llm_provider = llm_provider or get_llm_provider(
            model_name=settings.LLM_TITLE_MODEL or None
        )
        self.timeout = timeout if timeout is not None else settings.LLM_TITLE_TIMEOUT
        self.prompt_tpl = PROMPT_PATH.read_text(encoding="utf-8")

    async def generate_title(self, message: str, answer: str | None = None) -> TitleResult:
        fallback = TitleResult(title=fallback_title(message), source="fallback")
        # O mock não "entende" o assunto: usa direto o título de reserva.
        if getattr(self.llm_provider, "name", "") == "mock":
            return fallback

        prompt = self.prompt_tpl.format(
            question=message.strip()[:600],
            answer=(answer or "").strip()[:500],
        )
        try:
            response = await asyncio.wait_for(
                self.llm_provider.generate(prompt, temperature=0.2, max_tokens=24),
                timeout=self.timeout,
            )
        except (TimeoutError, RuntimeError):
            return fallback

        title = sanitize_title(response.content)
        if not title:
            return fallback
        return TitleResult(title=title, source="llm", model=response.model)
