"""Testes automatizados do runner de benchmark comparativo (Issue #24)."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "run_comparison", ROOT / "rag_benchmark/run_comparison.py"
)
run_comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_comparison)


def test_unified_retriever_indexa_todas_fontes_e_chunks():
    retriever = run_comparison.UnifiedCorpusRetriever()
    assert len(retriever.chunks) == 24
    assert retriever.store.count() == 24


def test_recuperacao_densa_naive_rag():
    retriever = run_comparison.UnifiedCorpusRetriever()
    hits = retriever.retrieve_dense("Como organizar o orçamento pessoal?", top_k=3)
    assert len(hits) <= 3
    assert len(hits) > 0
    # Chunks devem conter metadados e documento
    assert all(h.document_id for h in hits)
    assert all(h.score >= 0.0 for h in hits)


def test_recuperacao_hibrida_trokim_estruturado():
    retriever = run_comparison.UnifiedCorpusRetriever()
    hits = retriever.retrieve_hybrid("Como organizar o orçamento pessoal?", top_k=3, threshold=0.10)
    assert len(hits) <= 3
    assert len(hits) > 0
    # O primeiro resultado deve ser relevante ao orçamento
    assert any("orcamento" in h.document_id for h in hits)


def test_format_context_estrutura_blocos():
    retriever = run_comparison.UnifiedCorpusRetriever()
    sample = retriever.chunks[:2]
    formatted = run_comparison.format_context(sample)
    assert "[1] Órgão:" in formatted
    assert "Documento:" in formatted
    assert "Trecho:" in formatted


def test_cli_benchmark_executa_em_modo_mock(tmp_path):
    output_json = tmp_path / "results.json"
    report_json = tmp_path / "report.json"
    report_md = tmp_path / "report.md"
    chart_svg = tmp_path / "chart.svg"

    result = subprocess.run(
        [
            sys.executable,
            "../research/rag_benchmark/run_comparison.py",
            "--provider",
            "mock",
            "--limit",
            "3",
            "--output",
            str(output_json),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_md),
            "--chart-svg",
            str(chart_svg),
        ],
        cwd=ROOT.parent / "api",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_json.exists()
    assert report_json.exists()
    assert report_md.exists()
    assert chart_svg.exists()

    data = json.loads(output_json.read_text(encoding="utf-8"))
    assert len(data["cases"]) == 3
    for case in data["cases"]:
        responses = case["responses"]
        assert "llm_pura" in responses
        assert "rag_ingenuo" in responses
        assert "trokim_estruturado" in responses
        for _method, res in responses.items():
            assert "answer" in res
            assert "status" in res
            assert "latency_ms" in res
            assert isinstance(res["latency_ms"], (int, float))

    svg_content = chart_svg.read_text(encoding="utf-8")
    assert "<svg" in svg_content
    assert "</svg>" in svg_content
    assert "Inconsistência (Alucinação)" in svg_content
