"""Rastreabilidade das execuções do benchmark comparativo e dos gráficos publicados.

Cada execução fica em `results/comparison/<run_id>/` com um `run.json`. Estes testes
garantem que nenhuma execução entra sem metadados, que os números do `run.json` batem
com o relatório gerado pelo runner, que os gráficos existem e que a página de resultados
do MkDocs cita a execução.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNS = sorted((ROOT / "research/rag_benchmark/results/comparison").glob("*/run.json"))
ASSETS = ROOT / "docs/assets/comparacao"
PAGE = ROOT / "docs/pesquisa/resultados.md"
APPROACHES = ["llm_pura", "rag_ingenuo", "trokim_estruturado"]
REQUIRED = {
    "schema_version",
    "run_id",
    "date",
    "reference_commit",
    "issue",
    "model",
    "provider",
    "temperature",
    "top_k",
    "repetitions",
    "cases",
    "corpus",
    "raw_responses",
    "audit",
    "source_of_numbers",
    "approaches",
}
METRICS = ["f1_tokens", "concept_coverage", "inconsistency_rate", "abstention_f1"]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ha_execucoes_registradas():
    assert len(RUNS) >= 2


@pytest.mark.parametrize("path", RUNS, ids=lambda p: p.parent.name)
def test_run_json_completo_e_consistente(path):
    run = _load(path)
    assert REQUIRED <= set(run), f"faltam campos: {REQUIRED - set(run)}"
    assert run["run_id"] == path.parent.name
    assert run["run_id"].startswith(run["date"]), "o id da execução começa pela data"
    assert run["cases"] == 30
    expected = APPROACHES + (["multiagente"] if run["schema_version"] == 2 else [])
    assert list(run["approaches"]) == expected
    if run["schema_version"] == 2:
        assert run["multiagent_cases"] == 20
        assert run["multiagent"]["case_count"] == 20
        assert (ROOT / run["audit_pending"]).is_file()
        assert len(run["reference_commit"]) == 40
    for key, info in run["approaches"].items():
        for metric in METRICS:
            if info[metric] is None:
                assert run["schema_version"] == 2 and metric == "inconsistency_rate"
            else:
                assert 0 <= info[metric] <= 1, f"{key}.{metric} fora de [0, 1]"
        assert info["latency_ms"] > 0
        audit = info.get("audit")
        if run["audit"]:
            # Confirmadas incluem as que a heurística não sinalizou (falsos negativos).
            assert audit["false_positives"] <= audit["flagged"]
            assert audit["confirmed"] >= audit["flagged"] - audit["false_positives"]
            assert audit["confirmed"] <= run["cases"]


@pytest.mark.parametrize("path", RUNS, ids=lambda p: p.parent.name)
def test_numeros_batem_com_o_relatorio_gerado_pelo_runner(path):
    run = _load(path)
    if not run["raw_responses"]:
        pytest.skip("execução sem respostas brutas versionadas (registrada pelo relatório)")
    assert (ROOT / run["raw_responses"]).exists()
    report = _load(path.parent / "comparison_report.json")
    assert report["case_count"] == run["cases"]
    for key, info in run["approaches"].items():
        method = report["methods"][key]
        assert info["f1_tokens"] == pytest.approx(method["token_f1"], abs=1e-4)
        assert info["concept_coverage"] == pytest.approx(method["concept_recall"], abs=1e-4)
        assert info["inconsistency_rate"] == pytest.approx(
            method["factual_inconsistency_rate"], abs=1e-4
        )
        assert info["abstention_f1"] == pytest.approx(method["abstention_f1"], abs=1e-4)


@pytest.mark.parametrize("path", RUNS, ids=lambda p: p.parent.name)
def test_graficos_da_execucao_existem_e_estao_na_pagina(path):
    run = _load(path)
    figures = ["fig1-metricas.png", "fig3-latencia.png"]
    if run["audit"]:
        figures.append("fig2-alucinacao-auditada.png")
    if run["schema_version"] == 2:
        figures += [
            "fig4-falhas-por-caso.png",
            "fig5-acerto-numerico.png",
            "fig6-latencia-agentes.png",
        ]
    page = PAGE.read_text(encoding="utf-8")
    for name in figures:
        assert (ASSETS / run["run_id"] / name).stat().st_size > 1000, name
        assert f"assets/comparacao/{run['run_id']}/{name}" in page, name
    assert run["run_id"] in page


def test_graficos_da_semana2_e_da_variacao_existem_e_estao_na_pagina():
    page = PAGE.read_text(encoding="utf-8")
    for rel in (
        "semana2/fig-metas.png",
        "semana2/fig-calibracao-alpha.png",
        "entre-execucoes/fig-variacao-entre-execucoes.png",
    ):
        assert (ASSETS / rel).stat().st_size > 1000, rel
        assert f"assets/comparacao/{rel}" in page, rel


def test_calibracao_de_alpha_tem_series_do_mesmo_tamanho():
    data = _load(ROOT / "research/rag_benchmark/results/alpha_calibration.json")
    assert len(data["alpha"]) == len(data["recall_at_3"]) == len(data["grounded_accuracy"])
    assert data["chosen_alpha"] in data["alpha"]
