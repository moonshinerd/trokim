"""Benchmark e avaliação da base RAG do Trokim (Semana 2 do CBL).

Avalia taxa de recuperação correta e acurácia de abstenção contra um gabarito estruturado.
"""

import sys
from pathlib import Path

# Adiciona o diretório api ao path para importar o serviço RAG
api_path = Path(__file__).resolve().parents[2] / "api"
sys.path.insert(0, str(api_path))

from app.services.rag_service import RAGService  # noqa: E402

BENCHMARK_QUERIES = [
    {
        "query": "Como devo calcular a minha reserva de emergência?",
        "expected_source": "Banco Central do Brasil",
        "should_abstain": False,
    },
    {
        "query": "Qual a diferença entre despesas fixas e variáveis no orçamento?",
        "expected_source": "Banco Central do Brasil",
        "should_abstain": False,
    },
    {
        "query": "Como definir metas financeiras de curto, médio e longo prazo?",
        "expected_source": "Comissão de Valores Mobiliários (CVM)",
        "should_abstain": False,
    },
    {
        "query": "Quais os quatro pilares do bem-estar financeiro?",
        "expected_source": "Consumer Financial Protection Bureau (CFPB)",
        "should_abstain": False,
    },
    {
        "query": "Qual a receita tradicional do bolo de cenoura com cobertura?",
        "expected_source": None,
        "should_abstain": True,
    },
    {
        "query": "Quem foi o campeão da Copa do Mundo de futebol em 2002?",
        "expected_source": None,
        "should_abstain": True,
    },
]


def run_benchmark():
    rag = RAGService()
    print("=" * 60)
    print("Iniciando Benchmark RAG — Trokim (Semana 2)")
    print(f"Total de chunks na base: {len(rag.chunks)}")
    print("=" * 60)

    total = len(BENCHMARK_QUERIES)
    correct_retrievals = 0
    correct_abstentions = 0

    for idx, test_case in enumerate(BENCHMARK_QUERIES, 1):
        query = test_case["query"]
        expected_src = test_case["expected_source"]
        should_abstain = test_case["should_abstain"]

        result = rag.answer_query(query)
        answered = result["answered"]

        if should_abstain:
            if not answered:
                correct_abstentions += 1
                status = "PASS (Abstenção Correta)"
            else:
                status = "FAIL (Deveria ter se abstido)"
        else:
            evidences = result["evidences"]
            matched_source = any(expected_src in ev["source_name"] for ev in evidences)
            if answered and matched_source:
                correct_retrievals += 1
                status = "PASS (Recuperação Correta)"
            else:
                status = "FAIL (Fonte não encontrada)"

        print(f"[{idx}/{total}] {status} -> Pergunta: '{query}'")

    print("=" * 60)
    expected_valid = sum(1 for q in BENCHMARK_QUERIES if not q["should_abstain"])
    expected_abstain = sum(1 for q in BENCHMARK_QUERIES if q["should_abstain"])

    retrieval_acc = (correct_retrievals / expected_valid) * 100 if expected_valid else 0
    abstention_acc = (correct_abstentions / expected_abstain) * 100 if expected_abstain else 0

    print(
        f"Acurácia de Recuperação Fundamentada: {retrieval_acc:.1f}% "
        f"({correct_retrievals}/{expected_valid})"
    )
    print(
        f"Acurácia de Abstenção Ativa: {abstention_acc:.1f}% "
        f"({correct_abstentions}/{expected_abstain})"
    )
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
