"""Fronteiras do benchmark multiagente: unidades, preservação para auditoria, segurança do
registro e compatibilidade histórica (integra o PR #85)."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "rag_benchmark"))
import eval_comparison as evaluation  # noqa: E402
import multiagent_benchmark as benchmark  # noqa: E402
import run_comparison as runner  # noqa: E402
import run_multiagent  # noqa: E402

from app.clients.mock_llm import MockLLMProvider  # noqa: E402
from app.domain.models import EvidenceChunk  # noqa: E402
from app.models.llm_provider import LLMResponse  # noqa: E402
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


SOURCE = benchmark.ComparisonRAG(Retriever())


@pytest.mark.parametrize(
    ("answer", "value", "unit", "matched"),
    [
        ("Saldo R$ 6.107,90.", 6107.9, "BRL", True),
        ("Saldo 6107.9 BRL.", 6107.9, "BRL", True),
        ("Saldo R$ 61.079,00.", 6107.9, "BRL", False),
        ("Saldo R$ -10,00.", 10, "BRL", False),
        ("Saldo R$ -10,00.", -10, "BRL", True),
        ("Taxa de 38,66%.", 38.66, "%", True),
        ("Taxa de cerca de 38,7%.", 38.66, "%", True),
        ("Taxa de R$ 38,66.", 38.66, "%", False),
        ("Prazo de 24 meses.", 24, "meses", True),
        ("Prazo de 24 anos.", 24, "meses", False),
        ("Prazo de 13 meses.", 12, "meses", False),
        ("Veja [24].", 24, "meses", False),
    ],
)
def test_numeros_exigem_valor_sinal_e_unidade(answer, value, unit, matched):
    assert benchmark.numeric_matches(answer, {"value": value, "unit": unit}) is matched


def test_c29_recebe_os_totais_do_sistema_e_c30_nao():
    transactions = benchmark.legacy_transactions({"calculation_fixture": "resumo_centavos"})
    summary = CalculationService.calculate_summary(transactions)
    assert (summary.total_income, summary.total_expenses, summary.net_balance) == (0.3, 0.1, 0.2)
    assert benchmark.legacy_transactions({"calculation_fixture": "sem_resultado"}) == []


async def test_cenarios_livres_sem_gabarito_no_prompt_e_sem_extrato_nas_armadilhas():
    class RecordingLLM(MockLLMProvider):
        prompts: list = []
        parameters: list = []

        async def generate(self, prompt, **kwargs):
            self.prompts.append(prompt)
            self.parameters.append((kwargs.get("temperature"), kwargs.get("max_tokens")))
            return await super().generate(prompt, **kwargs)

    cases = benchmark.load_multiagent_cases()
    llm = RecordingLLM()
    free = await run_multiagent.run_free(cases, llm, 0.1, retriever=Retriever())
    assert len(free) == 20
    # Nenhum rascunho adversarial do gabarito chega ao modelo.
    drafts = [c["validation_fixture"]["draft_answer"] for c in cases if "validation_fixture" in c]
    assert not any(d in p for d in drafts for p in llm.prompts)
    assert llm.parameters and set(llm.parameters) == {(0.1, benchmark.MAX_TOKENS)}
    # M16 a M18 vão sem extrato (use_ledger falso): nenhum cálculo sai do Analysis.
    by_id = {row["id"]: row for row in free}
    for case_id in ("M16", "M17", "M18"):
        assert by_id[case_id]["calculations"] == []


async def test_ensaio_injetado_barra_com_o_codigo_e_guarda_o_rascunho():
    traps = [c for c in benchmark.load_multiagent_cases() if c["category"] == "armadilha"]
    injected = await run_multiagent.run_injected(traps)
    assert len(injected) == 5
    assert all(row["status"] == "rejected" and row["draft_retained"] for row in injected)
    assert all(row["drafts"] for row in injected)


async def test_modelo_indisponivel_fica_registrado_e_nao_vira_recusa_segura():
    class UnavailableLLM:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("Modelo indisponível")

    row = await benchmark.execute_multiagent(
        "Qual será o preço exato de uma ação brasileira daqui a um ano?", UnavailableLLM(), SOURCE
    )
    assert row["model_failed"]
    cases = benchmark.load_multiagent_cases()
    free = []
    for case in cases:
        failed = case["id"] == "M16"
        free.append(
            {
                "id": case["id"],
                **(row if failed else {**row, "model_failed": False, "steps": []}),
            }
        )
    injected = await run_multiagent.run_injected([c for c in cases if c["category"] == "armadilha"])
    report = run_multiagent.evaluate(cases, free, injected)
    m16 = next(d for d in report["free"]["case_details"] if d["id"] == "M16")
    assert m16["model_failed"] and not m16["status_ok"]
    assert report["free"]["model_failures"] == ["M16"]


async def test_recusa_perde_acerto_numerico():
    class EmptyRetriever:
        def retrieve_hybrid(self, *args, **kwargs):
            return []

    case = next(c for c in benchmark.load_multiagent_cases() if c["id"] == "M06")
    row = await benchmark.execute_multiagent(
        case["question"], MockLLMProvider(), benchmark.ComparisonRAG(EmptyRetriever())
    )
    assert row["status"] != "answered"
    assert row["llm_responses"] == []  # absteve-se antes de chamar o modelo
    assert not any(benchmark.numeric_matches(row["answer"], n) for n in case["expected_numbers"])


async def test_preserva_respostas_originais_de_cada_tentativa_antes_da_substituicao():
    originals = ["  Seu saldo é R$ 99999.\n", "Seu saldo é R$ 88888."]

    class InventedLLM:
        def __init__(self):
            self.responses = []

        async def generate(self, *args, **kwargs):
            response = LLMResponse(
                content=originals[len(self.responses)],
                model="teste",
                prompt_tokens=10,
                completion_tokens=8,
                raw={"fixture": True},
            )
            self.responses.append(response.model_dump(mode="json"))
            return response

    llm = InventedLLM()
    row = await benchmark.execute_multiagent("Como organizar meu orçamento?", llm, SOURCE)
    saved = json.loads(json.dumps(row))
    assert len(saved["llm_responses"]) == len(saved["drafts"]) == 2
    assert saved["llm_responses"] == llm.responses
    assert [r["content"] for r in saved["llm_responses"]] == originals
    # O texto inventado nunca chega ao rascunho validado nem à resposta.
    assert all("99999" not in d["answer"] and "88888" not in d["answer"] for d in saved["drafts"])
    assert "99999" not in saved["answer"] and "88888" not in saved["answer"]


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
    with pytest.raises(ValueError, match="multiagente"):
        evaluation.evaluate_comparison([case, second], raw, sources={})


def test_auditoria_nao_confirma_automaticamente_nem_sobrescreve(tmp_path):
    report = {
        "methods": {
            "multiagente": {
                "case_details": [
                    {"id": "C27", "factual_inconsistencies": []},
                    {"id": "C01", "factual_inconsistencies": ["Sinalização"]},
                    {"id": "C02", "factual_inconsistencies": []},
                ]
            }
        }
    }
    path = tmp_path / "audit_pending.json"
    benchmark.write_audit_template(path, benchmark.comparison_audit_rows(report))
    data = json.loads(path.read_text())
    assert {r["id"] for r in data["cases"]} == {"C27", "C01"}
    assert all(r["confirmed"] is None for r in data["cases"])
    assert data["reviewer"] is None
    with pytest.raises(FileExistsError):
        benchmark.write_audit_template(path, [])


def test_registro_recusa_mock_parcial_e_identificador_invalido(tmp_path):
    assert runner.main(["--multiagent", "--provider", "mock", "--run-id", "2026-11-18-x"]) == 2
    assert runner.main(["--limit", "2", "--run-id", "2026-11-18-x"]) == 2
    with pytest.raises(ValueError):
        benchmark.check_new_run("execucao-sem-data", tmp_path / "nova")


def test_registro_nunca_sobrescreve_execucao_publicada(tmp_path):
    publicada = tmp_path / "2026-11-18-publicada"
    publicada.mkdir()
    (publicada / "run.json").write_text("{}")
    with pytest.raises(FileExistsError):
        benchmark.check_new_run("2026-11-18-publicada", publicada)
    benchmark.check_new_run("2026-11-18-nova", tmp_path / "2026-11-18-nova")  # pasta nova: ok


def test_resumo_dos_cenarios_entra_uma_vez_no_run_json(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "RESULTS", tmp_path)
    run_dir = tmp_path / "comparison" / "2026-11-18-teste"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text("{}")
    report = {
        "case_count": 20,
        "free": {
            "status_ok": 13,
            "numbers_expected": 11,
            "numbers_reproduced": 8,
            "validation_block_rate": 0.15,
            "traps_safe": 3,
            "latency_mean_ms": 10.0,
        },
        "injected": {"blocked_with_expected_code": 5},
    }
    assert benchmark.add_scenarios_to_registry("2026-11-18-teste", report)
    with pytest.raises(FileExistsError):
        benchmark.add_scenarios_to_registry("2026-11-18-teste", report)
    assert benchmark.add_scenarios_to_registry("2026-11-18-teste", report, replace=True)
    assert not benchmark.add_scenarios_to_registry("2026-11-18-sem-run", report)
