import pytest

from app.clients.sqlite_vector_store import SQLiteVectorStore
from app.core.config import settings
from app.services.rag_service import RAGService


class FakeEmbedder:
    """Embedding determinístico sem rede para exercitar a camada lexical isoladamente."""

    name = "teste-deterministico"
    dimension = 2

    def __init__(self):
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 1.0]


@pytest.fixture
def rag(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RAG_HYBRID_ALPHA", 0.0)
    return RAGService(
        embedder=FakeEmbedder(),
        store=SQLiteVectorStore(tmp_path / "rag.db", dimension=2),
    )


def test_rag_retrieves_relevant_knowledge(rag):
    # Pergunta sobre reserva de emergência abordada no Caderno do BCB
    results = rag.retrieve_evidence("Como montar uma reserva de emergência?", top_k=2)

    assert len(results) > 0
    top_result = results[0]
    assert (
        "Reserva de Emergência" in top_result.section or "emergência" in top_result.content.lower()
    )
    assert top_result.score > 0.15


def test_rag_abstained_on_irrelevant_query(rag):
    # Pergunta sem relação com a base regulatória
    query = "Qual é a melhor receita de bolo de chocolate caseiro com cobertura de brigadeiro?"
    response = rag.answer_query(query)

    assert response["answered"] is False
    assert response["status"] == "abstained"
    assert "não possui evidências suficientes" in response["answer"]


def test_cabecalho_nao_e_evidencia(rag):
    assert rag.chunks
    assert all("FONTE:" not in chunk.content for chunk in rag.chunks)
    assert all(chunk.section != "Introdução" for chunk in rag.chunks)


def test_citacao_aponta_para_documento_oficial(rag):
    result = rag.answer_query("Como montar reserva de emergência?")
    evidence = result["evidences"][0]
    assert evidence["source_url"].startswith("https://www.gov.br/investidor/")
    assert evidence["source_url"] in result["answer"]
    assert evidence["content"] in result["answer"]


def test_guardrail_preserva_orientacao_educacional(rag):
    for query in [
        "Como proteger minha conta bancária com senhas?",
        "Como organizar receita mensal e despesas?",
        "Como planejar o orçamento para um curso de música?",
        "Devo desconfiar de retorno garantido?",
    ]:
        assert not rag._outside_scope(query)


def test_busca_vazia_e_topk_invalido_nao_retornam_evidencia(rag):
    assert rag.retrieve_evidence("", threshold=0) == []
    assert rag.retrieve_evidence("dívidas", top_k=0) == []
    assert rag.retrieve_evidence("dívidas", top_k=-1) == []


def test_topk_nao_repete_documentos(rag):
    results = rag.retrieve_evidence(
        "Como planejar orçamento e reserva de emergência?", top_k=10, threshold=0
    )
    assert len(results) > 1
    document_ids = [chunk.document_id for chunk in results]
    assert len(document_ids) == len(set(document_ids))
    assert [chunk.score for chunk in results] == sorted(
        (chunk.score for chunk in results), reverse=True
    )


def test_componente_denso_participa_do_score(tmp_path, monkeypatch):
    scores = []
    for alpha in (0.0, 0.5):
        monkeypatch.setattr(settings, "RAG_HYBRID_ALPHA", alpha)
        service = RAGService(
            embedder=FakeEmbedder(),
            store=SQLiteVectorStore(tmp_path / f"hybrid-{alpha}.db", dimension=2),
            threshold=0,
        )
        results = service.retrieve_evidence("Como montar uma reserva de emergência?", top_k=1)
        assert results
        scores.append(results[0].score)
    assert scores[1] == pytest.approx(scores[0] * 0.5, abs=0.0002)
