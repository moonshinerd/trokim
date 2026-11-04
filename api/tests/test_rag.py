from app.services.rag_service import RAGService


def test_rag_retrieves_relevant_knowledge():
    rag = RAGService()
    # Pergunta sobre reserva de emergência abordada no Caderno do BCB
    results = rag.retrieve_evidence("Como montar uma reserva de emergência?", top_k=2)

    assert len(results) > 0
    top_result = results[0]
    assert (
        "Reserva de Emergência" in top_result.section or "emergência" in top_result.content.lower()
    )
    assert top_result.score > 0.15


def test_rag_abstained_on_irrelevant_query():
    rag = RAGService()
    # Pergunta sem relação com a base regulatória
    query = "Qual é a melhor receita de bolo de chocolate caseiro com cobertura de brigadeiro?"
    response = rag.answer_query(query)

    assert response["answered"] is False
    assert response["status"] == "abstained"
    assert "não possui evidências suficientes" in response["answer"]
