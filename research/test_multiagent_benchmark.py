"""Fronteiras do benchmark: segurança, unidades, revisão e compatibilidade histórica."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "rag_benchmark"))
import eval_comparison as evaluation  # noqa: E402
import multiagent_benchmark as benchmark  # noqa: E402
import run_comparison as runner  # noqa: E402

from app.clients.mock_llm import MockLLMProvider  # noqa: E402
from app.domain.models import EvidenceChunk  # noqa: E402
from app.services.calculation_service import CalculationService  # noqa: E402


class Retriever:
    def retrieve_hybrid(self, query, **kwargs):
        return [
            EvidenceChunk(
                id="bcb_orcamento",
                document_id="bcb_orcamento.txt",
                source_name="BCB",
                document_title="Orçamento",
                section="Planejamento",
                content="Organizar receitas e despesas ajuda a planejar o orçamento.",
                score=0.9,
            )
        ]


@pytest.mark.parametrize(
    ("answer", "value", "unit", "matched"),
    [
        ("Saldo R$ 6.107,90.", 6107.9, "BRL", True),
        ("Saldo 6107.9 BRL.", 6107.9, "BRL", True),
        ("Saldo R$ 61.079,00.", 6107.9, "BRL", False),
        ("Saldo R$ -10,00.", 10, "BRL", False),
        ("Saldo R$ -10,00.", -10, "BRL", True),
        ("Taxa de 38,66%.", 38.66, "%", True),
        ("Taxa de R$ 38,66.", 38.66, "%", False),
        ("Prazo de 24 meses.", 24, "meses", True),
        ("Prazo de 24 anos.", 24, "meses", False),
        ("Veja [24].", 24, "meses", False),
    ],
)
def test_numeros_exigem_valor_sinal_e_unidade(answer, value, unit, matched):
    assert benchmark.numeric_matches(answer, {"value": value, "unit": unit}) is matched


def test_fixture_c29_preserva_centavos_e_c30_nao_recebe_ledger():
    transactions = benchmark.legacy_transactions({"calculation_fixture": "resumo_centavos"})
    summary = CalculationService.calculate_summary(transactions)
    assert (summary.total_income, summary.total_expenses, summary.net_balance) == (0.3, 0.1, 0.2)
    assert benchmark.legacy_transactions({"calculation_fixture": "sem_resultado"}) == []


async def test_cenarios_com_agentes_reais_e_ensaio_controlado_separado():
    class RecordingLLM(MockLLMProvider):
        prompts = []
        parameters = []

        async def generate(self, prompt, **kwargs):
            self.prompts.append(prompt)
            self.parameters.append((kwargs.get("temperature"), kwargs.get("max_tokens")))
            return await super().generate(prompt, **kwargs)

    cases = benchmark.load_multiagent_cases()
    llm = RecordingLLM()
    raw = await benchmark.run_multiagent_cases(cases, llm, Retriever())
    report = benchmark.evaluate_multiagent(cases, raw)
    assert len(raw["cases"]) == 20
    assert len(raw["controlled_validation"]) == 5
    assert report["controlled_validation"]["correct_blocks"] == 5
    assert report["correct_blocks_free"] is None
    assert all(d["confirmed"] is None for d in report["case_details"])
    assert not any("99.999" in prompt for prompt in llm.prompts)
    assert llm.parameters and set(llm.parameters) == {(0.1, 300)}
    assert all(row["response"]["drafts"] for row in raw["controlled_validation"])
    # M19 só é uma armadilha quando recebe o rascunho inventado. A pergunta
    # livre pede um saldo legítimo e não deve ser pontuada como recusa obrigatória.
    m19 = next(d for d in report["case_details"] if d["id"] == "M19")
    assert m19["safe_abstention"] is None


async def test_modelo_indisponivel_nao_vira_abstencao_segura():
    class UnavailableLLM:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("Modelo indisponível")

    with pytest.raises(RuntimeError, match="execução incompleta"):
        await benchmark.execute_multiagent(
            {"id": "M01", "question": "Como organizar meu orçamento?"},
            UnavailableLLM(),
            Retriever(),
        )


async def test_recusa_perde_acerto_numerico_e_nao_inventa_confirmacao():
    class EmptyRetriever:
        def retrieve_hybrid(self, *args, **kwargs):
            return []

    case = next(c for c in benchmark.load_multiagent_cases() if c["id"] == "M06")
    response = await benchmark.execute_multiagent(case, MockLLMProvider(), EmptyRetriever())
    report = benchmark.evaluate_multiagent(
        [case],
        {
            "cases": [{"id": case["id"], "response": response}],
            "controlled_validation": [],
        },
    )
    assert report["numeric_accuracy"] == 0
    assert report["validation_executed_cases"] == 0
    assert report["blocked_cases"] == 0
    assert "validation" not in report["latency_per_agent"]


def test_avaliador_preserva_tres_abordagens_e_exige_quarta_completa():
    case = {
        "id": "C01",
        "query": "Orçamento?",
        "expected_answer": "Planejar.",
        "concepts": [["planejar"]],
        "expected_behavior": "responder",
        "relevant": [],
    }
    responses = {
        key: {"answer": "Planejar.", "status": "grounded"}
        for key in ("llm_pura", "rag_ingenuo", "trokim_estruturado")
    }
    raw = {"cases": [{"id": "C01", "responses": responses}]}
    assert len(evaluation.evaluate_comparison([case], raw, sources={})["methods"]) == 3
    responses["multiagente"] = {"answer": "Não posso responder.", "status": "rejected"}
    report = evaluation.evaluate_comparison([case], raw, sources={})
    assert len(report["methods"]) == 4
    assert report["methods"]["multiagente"]["answered"] == 0
    assert "Multiagente" in evaluation.render_markdown(report)
    second = copy.deepcopy(case)
    second["id"] = "C02"
    raw["cases"].append(
        {"id": "C02", "responses": {k: v for k, v in responses.items() if k != "multiagente"}}
    )
    with pytest.raises(ValueError, match="resposta ausente para multiagente"):
        evaluation.evaluate_comparison([case, second], raw, sources={})


def test_auditoria_nao_confirma_automaticamente_nem_sobrescreve(tmp_path):
    report = {
        "methods": {
            "multiagente": {
                "case_details": [
                    {"id": "C27", "factual_inconsistencies": []},
                    {"id": "C01", "factual_inconsistencies": ["Sinalização"]},
                ]
            }
        },
        "multiagent": {"case_details": []},
    }
    path = tmp_path / "audit.json"
    benchmark.write_audit_template(report, path)
    data = json.loads(path.read_text())
    assert {r["id"] for r in data["cases"]} == {"C27", "C01"}
    assert all(r["confirmed"] is None for r in data["cases"])
    assert data["reviewer"] is None
    with pytest.raises(FileExistsError):
        benchmark.write_audit_template(report, path)


def test_registro_recusa_mock_antes_de_rodar_modelo():
    assert runner.main(["--multiagent", "--provider", "mock", "--run-id", "2026-11-18-teste"]) == 2


def test_auditoria_existente_impede_regenerar_respostas(tmp_path):
    path = tmp_path / "audit_pending.json"
    path.write_text("Revisão em andamento")
    assert runner.main(["--multiagent", "--report-json", str(tmp_path / "report.json")]) == 2
    assert path.read_text() == "Revisão em andamento"
    assert not (tmp_path / "report.json").exists()
