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


def test_cabecalho_nao_e_evidencia():
    rag = RAGService()
    assert rag.chunks
    assert all("FONTE:" not in chunk.content for chunk in rag.chunks)
    assert all(chunk.section != "Introdução" for chunk in rag.chunks)


def test_citacao_aponta_para_documento_oficial():
    result = RAGService().answer_query("Como montar reserva de emergência?")
    evidence = result["evidences"][0]
    assert evidence["source_url"].startswith("https://www.gov.br/investidor/")
    assert evidence["source_url"] in result["answer"]
    assert evidence["content"] in result["answer"]


def test_guardrail_preserva_orientacao_educacional():
    rag = RAGService()
    for query in [
        "Como proteger minha conta bancária com senhas?",
        "Como organizar receita mensal e despesas?",
        "Como planejar o orçamento para um curso de música?",
        "Devo desconfiar de retorno garantido?",
    ]:
        assert not rag._outside_scope(query)


def test_busca_vazia_e_topk_invalido_nao_retornam_evidencia():
    rag = RAGService()
    assert rag.retrieve_evidence("", threshold=0) == []
    assert rag.retrieve_evidence("dívidas", top_k=0) == []
    assert rag.retrieve_evidence("dívidas", top_k=-1) == []
