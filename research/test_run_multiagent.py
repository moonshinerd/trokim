"""Avaliador dos 20 cenários multiagente (#60), sem modelo: o ensaio injetado roda de verdade."""

import asyncio
import json

from rag_benchmark import run_multiagent as rm
from rag_benchmark.multiagent import QUESTIONS

CASES = json.loads(QUESTIONS.read_text(encoding="utf-8"))["cases"]


def _livre(case, status="answered", answer="Resposta."):
    agents = case["expected_agents"] if status == "answered" else ["research"]
    return {
        "id": case["id"],
        "status": status,
        "answer": answer,
        "latency_ms": 10.0,
        "validation_issues": []
        if status != "rejected"
        else [{"code": "NUMBER_NOT_SUPPORTED", "severity": "blocker", "message": "x"}],
        "steps": [{"agent": a, "status": "ok", "duration_ms": 5} for a in agents],
    }


def test_numeros_no_formato_brasileiro_e_com_ponto():
    assert rm.numbers_in("Saldo de R$ 6.107,90 e taxa de 38,66%") == [6107.90, 38.66]
    assert rm.number_reproduced("R$ 15.800,00", {"value": 15800.0, "unit": "BRL"})
    assert rm.number_reproduced("cerca de 38,7%", {"value": 38.66, "unit": "%"})
    assert not rm.number_reproduced("13 meses", {"value": 12, "unit": "meses"})


def test_avaliacao_conta_status_numeros_e_armadilhas():
    injetado = asyncio.run(rm.run_injected([c for c in CASES if c["category"] == "armadilha"]))
    livre = []
    for case in CASES:
        if case["category"] == "armadilha":
            livre.append(_livre(case, "abstained" if case["id"] != "M20" else "answered"))
        else:
            valores = " ".join(
                f"{n['value']:.2f}".replace(".", ",") for n in case["expected_numbers"]
            )
            livre.append(_livre(case, answer=f"{valores} {' '.join(case['required_concepts'])}"))
    report = rm.evaluate(CASES, livre, injetado)
    free = report["free"]
    assert free["regular_answered"] == 15
    assert free["agents_ok"] == 15
    assert free["numeric_accuracy"] == 1.0
    assert free["traps_safe"] == 4
    assert free["traps_needing_review"] == ["M20"]
    assert report["injected"]["blocked_with_expected_code"] == 5
    assert report["injected"]["drafts_retained"] == 5
    markdown = rm.render_markdown(report, "mock")
    assert "Ensaio livre" in markdown and "rascunho injetado" in markdown
