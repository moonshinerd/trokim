"""Adaptador LiteLLM: um único ponto para configurar qualquer modelo (local ou nuvem)."""

import litellm

from app.core.config import settings
from app.domain.models import EvidenceChunk
from app.models.llm_provider import LLMResponse

# Local-first: nenhuma telemetria nem callback externo do LiteLLM.
litellm.telemetry = False
litellm.drop_params = True  # ignora parâmetros que o modelo escolhido não aceita


class LiteLLMProvider:
    """Provedor genérico sobre o LiteLLM.

    O modelo é escolhido só por configuração (`LLM_MODEL`), no formato do LiteLLM:
    `ollama/qwen2.5`, `ollama/gemma4:26b`, `openai/gpt-4o-mini`,
    `anthropic/claude-sonnet-5-5`, `openrouter/meta-llama/llama-3.1-8b-instruct`...
    Modelos locais não enviam dados a terceiros; modelos de nuvem exigem
    `LLM_API_KEY` e, se for o caso, `LLM_API_BASE`.
    """

    name: str = "litellm"

    def __init__(
        self,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        raw = model or settings.LLM_MODEL
        # Sem prefixo de provedor, assume Ollama local (ex.: "qwen2.5").
        self.model = raw if "/" in raw else f"ollama/{raw}"
        self.api_base = (api_base if api_base is not None else settings.LLM_API_BASE) or None
        self.api_key = (api_key if api_key is not None else settings.LLM_API_KEY) or None
        self.timeout = timeout if timeout is not None else settings.LLM_TIMEOUT

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        context_chunks: list[EvidenceChunk] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        extra: dict[str, object] = {}
        if self.model.startswith(("ollama/", "ollama_chat/")) and not settings.LLM_THINKING:
            # Modelos locais com "thinking" (ex.: gemma4) gastariam os tokens raciocinando
            # e devolveriam texto vazio em respostas curtas, como o título.
            extra["think"] = False

        try:
            completion = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
                max_tokens=max_tokens,
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
                **extra,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Erro ao consultar o modelo '{self.model}' via LiteLLM: {exc}"
            ) from exc

        content = (completion.choices[0].message.content or "").strip()
        usage = getattr(completion, "usage", None)
        return LLMResponse(
            content=content,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            raw={"provider": "litellm"},
        )
