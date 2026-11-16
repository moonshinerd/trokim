"""Factory para instanciar o provedor de linguagem configurado."""

from app.clients.litellm_provider import LiteLLMProvider
from app.clients.mock_llm import MockLLMProvider
from app.clients.ollama_provider import OllamaProvider
from app.core.config import settings
from app.models.llm_provider import LLMProvider


def get_llm_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
) -> LLMProvider:
    """Retorna o provedor LLM configurado.

    - ``litellm`` (padrão): qualquer modelo suportado pelo LiteLLM, definido por ``LLM_MODEL``.
    - ``ollama``: cliente HTTP direto do Ollama local.
    - ``mock``: determinístico, para testes e CI.
    """
    selected = (provider_name or settings.LLM_PROVIDER).lower()
    selected_model = model_name or settings.LLM_MODEL

    if selected == "litellm":
        return LiteLLMProvider(model=selected_model)
    if selected == "ollama":
        return OllamaProvider(model=selected_model)
    return MockLLMProvider(model_name=selected_model)
