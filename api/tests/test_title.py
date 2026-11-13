"""Testes do nomeador de conversas, da camada LiteLLM e do 503 do /generate."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.clients.litellm_provider import LiteLLMProvider
from app.clients.llm_factory import get_llm_provider
from app.clients.mock_llm import MockLLMProvider
from app.clients.ollama_provider import OllamaProvider
from app.main import app
from app.models.llm_provider import LLMResponse
from app.routers.v1.chat import get_generation_service, get_title_service
from app.services.title_service import TitleService, fallback_title, sanitize_title


class FakeProvider:
    name = "fake"

    def __init__(self, content: str = "", error: Exception | None = None, delay: float = 0):
        self.content, self.error, self.delay = content, error, delay

    async def generate(self, prompt: str, **kwargs: object) -> LLMResponse:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return LLMResponse(content=self.content, model="fake-model")


# ---------- sanitização e título de reserva ----------


@pytest.mark.parametrize(
    ("raw", "esperado"),
    [
        ('"Reserva de emergência"', "Reserva de emergência"),
        ("Título: Organizar o orçamento mensal.", "Organizar o orçamento mensal"),
        ("**Dívidas no cartão de crédito**\nExplicação extra", "Dívidas no cartão de crédito"),
        ("um dois três quatro cinco seis sete oito", "Um dois três quatro cinco seis"),
        ("Reserva de Emergência: Como Guardar R$", "Reserva de Emergência: Como Guardar"),
        ("Dívidas com o", "Dívidas"),
        ("   ", ""),
    ],
)
def test_sanitize_title(raw: str, esperado: str) -> None:
    assert sanitize_title(raw) == esperado


def test_fallback_title_usa_primeiras_palavras_e_tem_padrao() -> None:
    assert fallback_title("Como montar uma reserva de emergência do zero hoje?") == (
        "Como montar uma reserva de emergência"
    )
    assert fallback_title("   ") == "Nova conversa"


# ---------- serviço ----------


@pytest.mark.asyncio
async def test_titulo_gerado_pelo_llm() -> None:
    service = TitleService(FakeProvider('"Reserva de emergência"'))
    result = await service.generate_title("O que é reserva de emergência?")
    assert (result.title, result.source, result.model) == (
        "Reserva de emergência",
        "llm",
        "fake-model",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider",
    [
        FakeProvider(error=RuntimeError("modelo fora do ar")),
        FakeProvider(content="   "),
        FakeProvider(content="Qualquer", delay=1.0),
    ],
)
async def test_titulo_de_reserva_quando_o_modelo_falha(provider: FakeProvider) -> None:
    service = TitleService(provider, timeout=0.05)
    result = await service.generate_title("Como organizar meu orçamento mensal?")
    assert result.source == "fallback"
    assert result.title == "Como organizar meu orçamento mensal"


@pytest.mark.asyncio
async def test_mock_usa_direto_o_titulo_de_reserva() -> None:
    result = await TitleService(MockLLMProvider()).generate_title("Como sair das dívidas?")
    assert result.source == "fallback"
    assert result.title == "Como sair das dívidas"


# ---------- endpoints ----------


def test_endpoint_title_e_validacao() -> None:
    app.dependency_overrides[get_title_service] = lambda: TitleService(
        FakeProvider("Rotativo do cartão")
    )
    try:
        client = TestClient(app)
        ok = client.post("/v1/chat/title", json={"message": "Como funciona o rotativo?"})
        assert ok.status_code == 200
        assert ok.json() == {"title": "Rotativo do cartão", "source": "llm", "model": "fake-model"}
        assert client.post("/v1/chat/title", json={"message": ""}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_generate_devolve_503_quando_o_modelo_esta_indisponivel() -> None:
    class Broken:
        async def generate_answer(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("Ollama 404")

    app.dependency_overrides[get_generation_service] = lambda: Broken()
    try:
        res = TestClient(app).post("/v1/chat/generate", json={"message": "O que é CET?"})
        assert res.status_code == 503
        assert "indisponível" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ---------- LiteLLM e factory ----------


@pytest.mark.asyncio
async def test_litellm_provider_monta_a_chamada_e_le_a_resposta() -> None:
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="  Olá  "))],
        usage=SimpleNamespace(prompt_tokens=7, completion_tokens=2),
    )
    with patch(
        "app.clients.litellm_provider.litellm.acompletion", new=AsyncMock(return_value=completion)
    ) as call:
        provider = LiteLLMProvider(model="qwen2.5", api_base="", api_key="")
        res = await provider.generate("oi", system_instruction="sistema", max_tokens=5)

    assert provider.model == "ollama/qwen2.5"  # sem prefixo assume Ollama local
    assert (res.content, res.model, res.prompt_tokens, res.completion_tokens) == (
        "Olá",
        "ollama/qwen2.5",
        7,
        2,
    )
    kwargs = call.await_args.kwargs
    assert kwargs["messages"][0] == {"role": "system", "content": "sistema"}
    assert kwargs["api_base"] is None and kwargs["api_key"] is None
    assert kwargs["max_tokens"] == 5
    assert kwargs["think"] is False  # modelos locais: sem raciocínio estendido


@pytest.mark.asyncio
async def test_litellm_nao_envia_think_para_modelos_de_nuvem() -> None:
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=None
    )
    with patch(
        "app.clients.litellm_provider.litellm.acompletion", new=AsyncMock(return_value=completion)
    ) as call:
        await LiteLLMProvider(model="openai/gpt-4o-mini", api_key="k").generate("oi")
    assert "think" not in call.await_args.kwargs


@pytest.mark.asyncio
async def test_litellm_provider_converte_falha_em_runtime_error() -> None:
    with patch(
        "app.clients.litellm_provider.litellm.acompletion",
        new=AsyncMock(side_effect=Exception("sem rede")),
    ):
        with pytest.raises(RuntimeError, match="LiteLLM"):
            await LiteLLMProvider(model="openai/gpt-4o-mini").generate("oi")


def test_factory_escolhe_o_provedor_pela_configuracao() -> None:
    assert isinstance(get_llm_provider("litellm", "openai/gpt-4o-mini"), LiteLLMProvider)
    assert isinstance(get_llm_provider("ollama", "qwen2.5"), OllamaProvider)
    assert isinstance(get_llm_provider("mock"), MockLLMProvider)


def test_titulo_usa_o_modelo_leve_quando_configurado() -> None:
    with patch("app.services.title_service.settings.LLM_TITLE_MODEL", "ollama/qwen2.5:1.5b"):
        assert TitleService().llm_provider.model == "ollama/qwen2.5:1.5b"
    with patch("app.services.title_service.settings.LLM_TITLE_MODEL", ""):
        assert TitleService().llm_provider.model == get_llm_provider().model
