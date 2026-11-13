"""Testes unitários e de integração para a camada de síntese generativa (Issue #23)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from test_rag import FakeEmbedder

from app.clients.llm_factory import get_llm_provider
from app.clients.mock_llm import MockLLMProvider
from app.clients.ollama_provider import OllamaProvider
from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.domain.models import EvidenceChunk
from app.main import app
from app.services.generation_service import ABSTENTION_MESSAGE, GenerationService
from app.services.rag_service import RAGService


@pytest.fixture
def endpoint_service(tmp_path) -> GenerationService:
    rag = RAGService(
        embedder=FakeEmbedder(),
        store=SQLiteVectorStore(tmp_path / "generation.db", dimension=2),
    )
    return GenerationService(
        rag_service=rag,
        llm_provider=MockLLMProvider(model_name="qwen2.5-mock"),
    )


@pytest.fixture
def sample_chunk() -> EvidenceChunk:
    return EvidenceChunk(
        id="bcb_reserva_1",
        document_id="bcb_reserva.txt",
        source_name="Banco Central do Brasil",
        source_url="https://www.bcb.gov.br",
        document_title="Reserva de Emergência e Planejamento",
        section="Conceito e Dimensionamento",
        content=(
            "A reserva de emergência deve cobrir de 3 a 6 meses de despesas básicas "
            "em liquidez diária."
        ),
        score=0.92,
    )


@pytest.mark.asyncio
async def test_mock_llm_provider_with_context(sample_chunk: EvidenceChunk) -> None:
    provider = MockLLMProvider(model_name="qwen2.5-mock")
    response = await provider.generate(
        prompt="Como montar reserva?",
        context_chunks=[sample_chunk],
    )
    assert response.model == "qwen2.5-mock"
    assert "Banco Central do Brasil" in response.content
    assert "3 a 6 meses" in response.content
    assert response.completion_tokens > 0


@pytest.mark.asyncio
async def test_mock_llm_provider_pure_prompt() -> None:
    provider = MockLLMProvider(model_name="qwen2.5-mock")
    response = await provider.generate(
        prompt="Qual a taxa Selic?",
        context_chunks=None,
    )
    assert response.model == "qwen2.5-mock"
    assert "Síntese informativa geral" in response.content
    assert response.raw.get("simulated") is True


@pytest.mark.asyncio
async def test_ollama_provider_success() -> None:
    from unittest.mock import MagicMock

    mock_payload = {
        "response": "Para compor a reserva, priorize ativos com liquidez diária.",
        "prompt_eval_count": 25,
        "eval_count": 14,
        "total_duration": 1200000000,
        "load_duration": 300000000,
    }

    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5", timeout=5.0)

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_payload
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        res = await provider.generate("Como investir?")
        assert res.model == "qwen2.5"
        assert res.content == "Para compor a reserva, priorize ativos com liquidez diária."
        assert res.prompt_tokens == 25
        assert res.completion_tokens == 14


@pytest.mark.asyncio
async def test_ollama_provider_http_error() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5", timeout=2.0)

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate("teste")
        assert "Erro de comunicação com o Ollama local" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_provider_availability() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_res = AsyncMock()
        mock_res.status_code = 200
        mock_get.return_value = mock_res
        assert await provider.is_available() is True

    with patch("httpx.AsyncClient.get", side_effect=Exception("Timeout")):
        assert await provider.is_available() is False


def test_llm_factory() -> None:
    mock_p = get_llm_provider("mock", model_name="qwen2.5")
    assert isinstance(mock_p, MockLLMProvider)
    assert mock_p.model_name == "qwen2.5"

    ollama_p = get_llm_provider("ollama", model_name="qwen2.5:7b")
    assert isinstance(ollama_p, OllamaProvider)
    assert ollama_p.model == "qwen2.5:7b"


@pytest.mark.asyncio
async def test_generation_service_grounded_success(sample_chunk: EvidenceChunk) -> None:
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag._outside_scope = lambda _: False
    mock_rag.retrieve_evidence = lambda _query, top_k=None, threshold=None: [sample_chunk]

    mock_llm = MockLLMProvider(model_name="qwen2.5-mock")
    service = GenerationService(rag_service=mock_rag, llm_provider=mock_llm)

    result = await service.generate_answer("Como montar reserva de emergência?", mode="grounded")
    assert result.answered is True
    assert result.status == "grounded"
    assert result.mode == "grounded"
    assert len(result.evidences) == 1
    assert "Banco Central do Brasil" in result.answer


@pytest.mark.asyncio
async def test_generation_service_abstention_outside_scope() -> None:
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag._outside_scope = lambda _: True

    mock_llm = AsyncMock(spec=MockLLMProvider)
    service = GenerationService(rag_service=mock_rag, llm_provider=mock_llm)

    result = await service.generate_answer("Escreva um poema sobre flores", mode="grounded")
    assert result.answered is False
    assert result.status == "abstained"
    assert result.answer == ABSTENTION_MESSAGE
    assert result.evidences == []
    # Garante que a LLM NÃO foi chamada em consultas fora de escopo (zero alucinação)
    mock_llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_generation_service_abstention_no_evidence() -> None:
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag._outside_scope = lambda _: False
    mock_rag.retrieve_evidence = lambda _query, top_k=None, threshold=None: []

    mock_llm = AsyncMock(spec=MockLLMProvider)
    service = GenerationService(rag_service=mock_rag, llm_provider=mock_llm)

    result = await service.generate_answer("Tema sem evidência alguma", mode="grounded")
    assert result.answered is False
    assert result.status == "abstained"
    assert result.answer == ABSTENTION_MESSAGE
    mock_llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_generation_service_pure_mode() -> None:
    mock_rag = AsyncMock(spec=RAGService)
    mock_llm = MockLLMProvider(model_name="qwen2.5-mock")
    service = GenerationService(rag_service=mock_rag, llm_provider=mock_llm)

    result = await service.generate_answer("O que é inflação?", mode="pure")
    assert result.answered is True
    assert result.status == "pure_baseline"
    assert result.mode == "pure"
    assert result.evidences == []
    assert len(result.answer) > 0


@pytest.mark.asyncio
async def test_generation_service_naive_mode(sample_chunk: EvidenceChunk) -> None:
    mock_rag = AsyncMock(spec=RAGService)
    mock_rag.retrieve_evidence = lambda _query, top_k=None, threshold=None: [sample_chunk]
    mock_llm = MockLLMProvider(model_name="qwen2.5-mock")
    service = GenerationService(rag_service=mock_rag, llm_provider=mock_llm)

    result = await service.generate_answer("Como investir?", mode="naive")
    assert result.answered is True
    assert result.status == "naive_rag"
    assert result.mode == "naive"
    assert len(result.evidences) == 1


def test_endpoint_generate_grounded(endpoint_service: GenerationService) -> None:
    from app.routers.v1.chat import get_generation_service

    app.dependency_overrides[get_generation_service] = lambda: endpoint_service
    try:
        client = TestClient(app)
        payload = {
            "message": "Como planejar um orçamento mensal?",
            "mode": "grounded",
            "top_k": 2,
        }
        response = client.post("/v1/chat/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "Como planejar um orçamento mensal?"
        assert data["status"] in ("grounded", "abstained")
        assert "answer" in data
        assert "model" in data
    finally:
        app.dependency_overrides.pop(get_generation_service, None)


def test_endpoint_generate_abstained(endpoint_service: GenerationService) -> None:
    from app.routers.v1.chat import get_generation_service

    app.dependency_overrides[get_generation_service] = lambda: endpoint_service
    try:
        client = TestClient(app)
        payload = {
            "message": "Escreva um poema de futebol e receita de bolo",
            "mode": "grounded",
        }
        response = client.post("/v1/chat/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["answered"] is False
        assert data["status"] == "abstained"
        assert data["evidences"] == []
    finally:
        app.dependency_overrides.pop(get_generation_service, None)


def test_endpoint_generate_pure(endpoint_service: GenerationService) -> None:
    from app.routers.v1.chat import get_generation_service

    app.dependency_overrides[get_generation_service] = lambda: endpoint_service
    try:
        client = TestClient(app)
        payload = {
            "message": "Qual é a fórmula de juros compostos?",
            "mode": "pure",
        }
        response = client.post("/v1/chat/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["answered"] is True
        assert data["status"] == "pure_baseline"
        assert data["evidences"] == []
    finally:
        app.dependency_overrides.pop(get_generation_service, None)
