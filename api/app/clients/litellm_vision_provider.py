"""Modelo de visão pela camada LiteLLM: Ollama local ou OpenRouter, só por configuração."""

import base64
import json

import litellm

from app.core.config import settings
from app.models.vision_provider import VisionResult

litellm.telemetry = False
litellm.drop_params = True

LOCAL_PREFIXES = ("ollama/", "ollama_chat/")
# host.docker.internal é a própria máquina do usuário vista de dentro do contêiner.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]", "0.0.0.0", "host.docker.internal")


def is_remote_model(model: str, api_base: str | None) -> bool:
    """Um modelo é remoto se sai do aparelho: não é Ollama ou o endereço não é a própria máquina."""
    if not model.startswith(LOCAL_PREFIXES):
        return True
    if not api_base:
        return False
    host = api_base.split("://", 1)[-1].split("/", 1)[0].rsplit(":", 1)[0]
    return host not in LOCAL_HOSTS


def _mime(image: bytes) -> str:
    if image.startswith(b"\x89PNG"):
        return "image/png"
    return "image/jpeg"


class LiteLLMVisionProvider:
    name: str = "litellm"

    def __init__(
        self,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        raw = model or settings.VISION_MODEL
        self.model = raw if "/" in raw else f"ollama/{raw}"
        self.api_base = (api_base if api_base is not None else settings.VISION_API_BASE) or None
        self.api_key = (api_key if api_key is not None else settings.VISION_API_KEY) or None
        self.timeout = timeout if timeout is not None else settings.VISION_TIMEOUT
        self.is_remote = is_remote_model(self.model, self.api_base)

    async def extract(
        self,
        image: bytes,
        instructions: str,
        schema: dict[str, object] | None = None,
    ) -> VisionResult:
        prompt = instructions
        if schema:
            prompt += "\n\nResponda só com JSON neste esquema:\n" + json.dumps(
                schema, ensure_ascii=False
            )
        data_url = f"data:{_mime(image)};base64,{base64.b64encode(image).decode('ascii')}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]
        try:
            completion = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=0.0,
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        except Exception as exc:
            # A mensagem não inclui a imagem nem o conteúdo enviado.
            raise RuntimeError(
                f"Erro ao consultar o modelo de visão '{self.model}': {type(exc).__name__}"
            ) from exc
        usage = getattr(completion, "usage", None)
        return VisionResult(
            content=(completion.choices[0].message.content or "").strip(),
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
