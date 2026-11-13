"""Testes determinísticos das métricas comparativas, sem chamadas a provedores."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "eval_comparison", ROOT / "rag_benchmark/eval_comparison.py"
)
eval_comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_comparison)


def test_token_f1_normaliza_artigos_acentos_pontuacao_e_multiconjunto():
    assert eval_comparison.token_f1("A reserva é importante!", "reserva e importante") == 1
    assert eval_comparison.token_f1("gasto gasto saldo", "gasto saldo saldo") == 2 / 3
    assert eval_comparison.token_f1("", "") == 1
    assert eval_comparison.token_f1("reserva", "liquidez") == 0


def test_concept_recall_aceita_alternativas_por_grupo():
    answer = "A reserva exige liquidez diária e baixo risco."
    concepts = [["liquidez imediata", "liquidez diária"], ["baixo risco"], ["garantia"]]

    assert eval_comparison.concept_recall(answer, concepts) == 2 / 3
    assert eval_comparison.concept_recall(answer, []) is None


def test_concept_recall_reconhece_flexoes_regulares_ptbr():
    answer = "Diversificar reduz riscos e o teto vale para operações originadas nesta data."
    concepts = [["reduzir riscos"], ["operação"]]

    assert eval_comparison.concept_recall(answer, concepts) == 1


def test_numeric_facts_compara_moeda_e_separadores_ptbr():
    case = {
        "query": "Qual é o limite?",
        "expected_answer": "O limite da operação é R$ 2.000,00.",
        "forbidden_claims": [],
    }
    source = "O período máximo é de 1.000 dias."

    assert (
        eval_comparison.factual_inconsistencies(
            "O limite é R$ 2.000,00 e o prazo é 1000 dias.", case, [source]
        )
        == []
    )


def test_numeric_fact_divergente_e_sinalizado():
    case = {
        "query": "Qual é o limite?",
        "expected_answer": "O limite da operação é R$ 2.000,00.",
        "forbidden_claims": [],
    }

    findings = eval_comparison.factual_inconsistencies("O limite é R$ 2.500,00.", case, [])

    assert findings == ["número sem suporte: 2500 (moeda)"]


def test_contradicao_por_negacao_e_sinalizada():
    case = {
        "query": "A rentabilidade passada garante retorno futuro?",
        "expected_answer": "Rentabilidade passada não garante retorno futuro.",
        "forbidden_claims": [],
    }

    findings = eval_comparison.factual_inconsistencies(
        "Rentabilidade passada garante retorno futuro.", case, []
    )

    assert any("contradição por negação" in finding for finding in findings)


def test_equivalencias_negativas_e_limites_de_clausula_nao_sao_contradicoes():
    case = {
        "query": "Pergunta",
        "expected_answer": "",
        "forbidden_claims": [],
    }

    no_waiting_period = eval_comparison.factual_inconsistencies(
        "Priorizar baixo risco e liquidez, sem carência.",
        case,
        ["Priorize baixo risco, liquidez diária e ausência de carência."],
    )
    no_free_credit = eval_comparison.factual_inconsistencies(
        "Não. O prazo limita o uso do rotativo até a fatura subsequente, "
        "não concede gratuidade; há juros e encargos contratuais.",
        case,
        [
            "O financiamento vai até a fatura subsequente. Essa duração não é uma "
            "carência gratuita: há juros e encargos contratuais."
        ],
    )

    assert no_waiting_period == []
    assert no_free_credit == []


def test_frase_proibida_literal_e_sinalizada():
    phrase = "promessa de retorno garantido"
    case = {
        "query": "Há promessa de retorno garantido?",
        "expected_answer": "A frase deve ser evitada.",
        "forbidden_claims": [phrase],
    }

    findings = eval_comparison.factual_inconsistencies(
        "A resposta contém promessa de retorno garantido.", case, []
    )

    assert findings == [f"afirmação proibida literal: {phrase}"]


def test_abstention_f1_calcula_matriz_binaria():
    metrics = eval_comparison.abstention_metrics(
        [True, False, True, False], [True, True, False, False]
    )

    assert metrics == {
        "tp": 1,
        "fp": 1,
        "fn": 1,
        "tn": 1,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
    }


def test_relatorio_compara_tres_abordagens_sem_servico_externo(tmp_path):
    cases = [
        {
            "id": "C01",
            "query": "Como agir?",
            "expected_answer": "Rentabilidade passada não garante retorno futuro.",
            "concepts": [["rentabilidade passada"], ["retorno futuro"]],
            "relevant": ["cvm.txt"],
            "expected_behavior": "responder",
            "forbidden_claims": [],
        },
        {
            "id": "C02",
            "query": "Qual ação vai subir amanhã?",
            "expected_answer": "Não há evidência suficiente para prever isso.",
            "concepts": [["evidência suficiente"]],
            "relevant": [],
            "expected_behavior": "abster",
            "forbidden_claims": [],
        },
    ]
    supported = "Rentabilidade passada não garante retorno futuro."
    abstention = {
        "answer": "Não há evidência suficiente para prever isso.",
        "answered": False,
        "status": "abstained",
    }
    results = {
        "cases": [
            {
                "id": "C01",
                "responses": {
                    "llm_pura": {
                        "answer": supported,
                        "answered": True,
                        "status": "pure_baseline",
                    },
                    "rag_ingenuo": {
                        "answer": supported,
                        "answered": True,
                        "status": "naive_rag",
                    },
                    "trokim_estruturado": {
                        "answer": supported,
                        "answered": True,
                        "status": "grounded",
                    },
                },
            },
            {
                "id": "C02",
                "responses": {
                    "llm_pura": abstention,
                    "rag_ingenuo": {
                        "answer": "A ação vai subir 50%.",
                        "answered": True,
                        "status": "naive_rag",
                    },
                    "trokim_estruturado": abstention,
                },
            },
        ]
    }

    report = eval_comparison.evaluate_comparison(cases, results, sources={"cvm.txt": supported})

    assert report["case_count"] == 2
    assert set(report["methods"]) == {
        "llm_pura",
        "rag_ingenuo",
        "trokim_estruturado",
    }
    assert report["methods"]["trokim_estruturado"]["token_f1"] == 1
    assert report["methods"]["trokim_estruturado"]["abstention_f1"] == 1
    assert report["methods"]["rag_ingenuo"]["factual_inconsistency_rate"] == 0.5


def test_cli_grava_json_e_markdown(tmp_path):
    case = {
        "id": "C01",
        "query": "Pergunta",
        "expected_answer": "Resposta de referência.",
        "concepts": [["referência"]],
        "relevant": [],
        "expected_behavior": "responder",
        "forbidden_claims": [],
    }
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps({"schema_version": 1, "cases": [case]}))
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "C01",
                        "responses": {
                            method: {
                                "answer": "Resposta de referência.",
                                "status": "grounded",
                            }
                            for method in eval_comparison.METHODS
                        },
                    }
                ]
            }
        )
    )
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"

    exit_code = eval_comparison.main(
        [
            "--cases",
            str(cases_path),
            "--results",
            str(results_path),
            "--json-output",
            str(json_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(json_path.read_text())["case_count"] == 1
    assert "Abstention F1" in markdown_path.read_text()


def test_resultados_incompletos_sao_rejeitados():
    cases = [
        {
            "id": "C01",
            "query": "Q",
            "expected_answer": "A",
            "concepts": [],
            "relevant": [],
        }
    ]
    results = {
        "cases": [
            {
                "id": "C01",
                "responses": {"llm_pura": {"answer": "A", "status": "grounded"}},
            }
        ]
    }

    try:
        eval_comparison.evaluate_comparison(cases, results, sources={})
    except ValueError as error:
        assert "resposta ausente" in str(error)
    else:
        raise AssertionError("O avaliador aceitou abordagens ausentes.")
