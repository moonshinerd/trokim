"""Gráficos dos motores e do chat: ramos novo e legado sem sobrescrever nada."""

import json

from rag_benchmark import document_charts


def _split(**over):
    base = {
        "documents": 20,
        "completed_documents": 20,
        "correct_fields": 40,
        "recoverable_fields": 50,
        "wrong_fields": 8,
        "missing_fields": 2,
        "invented_fields": 1,
        "correct_documents": 10,
        "technical_failures": 2,
        "illegible_documents": 4,
        "safe_abstentions": 3,
        "false_accepts": 1,
        "per_field": {
            key: {"correct": correct, "expected": 10, "accuracy": correct / 10}
            for key, correct in (
                ("amount", 8),
                ("date", 7),
                ("counterparty", 6),
                ("total", 9),
                ("due_date", 5),
                ("bank", 5),
            )
        },
        "field_accuracy": 0.8,
        "document_accuracy": 0.5,
        "safe_abstention_rate": 0.75,
        "latency_ms": {"mean": 1200.0, "p95": 4000.0},
        "usage": {
            "calls": 12,
            "prompt_tokens": 30000,
            "completion_tokens": 4000,
            "estimated_cost_usd": None,
            "cost_status": "não calculado",
        },
        "by_degradation": {
            "blur:mild": {"correct_fields": 10, "recoverable_fields": 12, "documents": 3},
            "noise:severe": {"correct_fields": 4, "recoverable_fields": 10, "documents": 2},
        },
    }
    base.update(over)
    return base


def engine_run():
    return {
        "engine": "ocr+vlm-local",
        "model": "ollama/mistral-small3.2:24b",
        "summary": {"calibration": _split(), "validation": _split(correct_fields=30)},
    }


def legacy_run(mode="rapidocr"):
    return {
        "mode": mode,
        "summary": {
            split: {
                "documents": 20,
                "gate": {
                    "readable_accepted": 15,
                    "readable_rejected": 1,
                    "illegible_accepted": 0,
                    "illegible_rejected": 4,
                },
                "correct_fields": 40,
                "recoverable_fields": 50,
                "correct_transactions": 30,
                "recoverable_transactions": 60,
            }
            for split in ("calibration", "validation")
        },
    }


def test_engine_run_gera_graficos_novos_sem_porteiro(tmp_path):
    document_charts.engine_charts(engine_run(), tmp_path)
    for name in ("campos", "acertos", "riscos", "degradacao", "latencia"):
        assert (tmp_path / f"{name}.svg").exists(), name
    assert not (tmp_path / "qualidade.svg").exists()
    assert "8/10" in (tmp_path / "campos.svg").read_text(encoding="utf-8")


def test_engine_run_sem_degradacao_omite_grafico(tmp_path):
    run = engine_run()
    for split in run["summary"].values():
        split["by_degradation"] = {}
    document_charts.engine_charts(run, tmp_path)
    assert not (tmp_path / "degradacao.svg").exists()
    assert (tmp_path / "campos.svg").exists()


def test_legado_preserva_porteiro_e_extracao(tmp_path):
    run = legacy_run()
    document_charts.gate_chart(run, tmp_path)
    document_charts.extraction_chart(run, tmp_path)
    assert (tmp_path / "qualidade.svg").exists()
    assert (tmp_path / "extracao.svg").exists()


def test_extracao_ignora_modo_sem_ocr(tmp_path):
    document_charts.extraction_chart(legacy_run(mode="quality_only"), tmp_path)
    assert not (tmp_path / "extracao.svg").exists()


def test_main_despacha_por_engine(tmp_path, monkeypatch):
    results = tmp_path / "research/rag_benchmark/results/documents"
    (results / "novo").mkdir(parents=True)
    (results / "antigo").mkdir(parents=True)
    (results / "novo/run.json").write_text(json.dumps(engine_run()), encoding="utf-8")
    (results / "antigo/run.json").write_text(json.dumps(legacy_run()), encoding="utf-8")
    monkeypatch.setattr(document_charts, "ROOT", tmp_path)
    document_charts.main()
    base = tmp_path / "docs/assets/documentos"
    assert (base / "novo/campos.svg").exists()
    assert not (base / "novo/qualidade.svg").exists()
    assert (base / "antigo/qualidade.svg").exists()
    assert (base / "antigo/extracao.svg").exists()
