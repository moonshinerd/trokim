"""Adaptador para Ollama local-first (executando Qwen localmente)."""

import httpx

from app.core.config import settings
from app.domain.models import EvidenceChunk
from app.models.llm_provider import LLMResponse


class OllamaProvider:
    """Cliente HTTP assíncrono para Ollama local (ex.: qwen2.5) sem envio de dados a terceiros."""

    name: str = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.LLM_API_BASE).rstrip("/")
        raw_model = model or settings.LLM_MODEL
        # Normaliza caso venha prefixado com "ollama/"
        self.model = raw_model.split("/")[-1] if "/" in raw_model else raw_model
        self.timeout = timeout if timeout is not None else settings.LLM_TIMEOUT

    async def is_available(self) -> bool:
        """Verifica se o servidor Ollama local está ativo e responsivo."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        context_chunks: list[EvidenceChunk] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Envia prompt para o modelo Qwen local no Ollama e retorna síntese."""
        options: dict[str, object] = {
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
        }
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "system": system_instruction or "",
            "stream": False,
            "options": options,
        }

        url = f"{self.base_url}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Erro de comunicação com o Ollama local em {url} (modelo '{self.model}'): {exc}"
            ) from exc

        content = data.get("response", "").strip()
        return LLMResponse(
            content=content,
            model=self.model,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            raw={
                "provider": "ollama",
                "total_duration_ns": data.get("total_duration"),
                "load_duration_ns": data.get("load_duration"),
            },
        )
