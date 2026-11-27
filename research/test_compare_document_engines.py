"""Protocolo multimodal validado sem rede e sem inferência real."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from rag_benchmark import compare_document_engines as benchmark

from app.clients.mock_vision import MockVisionProvider
from app.models.vision_provider import OcrResult, VisionResult


def case(identifier="D01", bad=False):
    return {
        "id": identifier,
        "split": "validation",
        "expected_quality": "illegible" if bad else "legible",
        "recoverable_fields": {} if bad else {"amount": "10.00"},
        "recoverable_transactions": [],
        "degradation": {"type": "blur", "level": "severe"},
    }


def row(identifier="D01", bad=False, failed=False):
    return {
        "id": identifier,
        "latency_ms": 10,
        "technical_failures": ["VISION_UNAVAILABLE"] if failed else [],
        "document": {
            "abstained": bad,
            "fields": [] if bad else [{"key": "amount", "value": "10.00"}],
            "transactions": [],
        },
    }


def test_technical_failure_never_counts_as_success():
    score = benchmark.metrics([case()], [row(failed=True)])
    assert score["correct_fields"] == score["correct_documents"] == 0
    assert score["technical_failures"] == 1
    score = benchmark.metrics([case(bad=True)], [row(bad=True, failed=True)])
    assert score["safe_abstentions"] == 0


def test_false_accept_invented_and_wrong_are_separate():
    actual = row()
    actual["document"]["fields"][0]["value"] = "11.00"
    actual["document"]["fields"].append({"key": "bank", "value": "Inventado"})
    score = benchmark.metrics([case()], [actual])
    assert score["wrong_fields"] == score["invented_fields"] == 1
    score = benchmark.metrics([case(bad=True)], [row()])
    assert score["false_accepts"] == 1
    assert score["safe_abstentions"] == 0


def test_correct_abstention_and_split_degradation():
    report = benchmark.summarize([case(bad=True)], [row(bad=True)])
    assert report["validation"]["safe_abstention_rate"] == 1
    assert report["calibration"]["documents"] == 0
    assert report["validation"]["by_degradation"]["blur:severe"]["correct_documents"] == 1


def test_pending_rows_not_successes_and_duplicate_ids_rejected():
    score = benchmark.metrics([case(), case("D02")], [row()])
    assert score["document_accuracy"] == 0.5
    assert score["completed_documents"] == 1
    with pytest.raises(ValueError):
        benchmark.metrics([case()], [row(), row()])


def test_existing_run_refused_before_any_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(
        benchmark, "build_agent", lambda *args: pytest.fail("Motor não deveria ser criado")
    )
    with pytest.raises(ValueError, match="já existe"):
        asyncio.run(benchmark.run(tmp_path, "ocr"))


def test_remote_requires_explicit_consent(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Remoto exige"):
        benchmark.build_agent("ocr+vlm-remoto", "openrouter/mock", None, 600)
    with pytest.raises(ValueError, match="local exige"):
        benchmark.build_agent("ocr+vlm-local", "openrouter/mock", None, 600)
    with pytest.raises(ValueError, match="incompatível"):
        benchmark.build_agent("ocr+vlm-local", None, "https://example.org:443", 600)


def test_vision_audit_preserves_raw_and_tokens(monkeypatch):
    raw = VisionResult(content='{"fields":[]}', model="mock", prompt_tokens=20, completion_tokens=5)
    monkeypatch.setattr(benchmark.LiteLLMVisionProvider, "extract", AsyncMock(return_value=raw))
    monkeypatch.setattr(benchmark.litellm, "cost_per_token", lambda **kwargs: (0.002, 0.0005))
    provider = benchmark.AuditedVision(model="ollama/mock", api_base="http://127.0.0.1:11434")
    assert asyncio.run(provider.extract(b"synthetic", "campos")) == raw
    assert provider.readings[0]["result"]["prompt_tokens"] == 20
    assert provider.readings[0]["estimated_cost_usd"] == pytest.approx(0.0025)
    assert "litellm" in provider.readings[0]["cost_status"]


def test_cost_unavailable_is_explicit_null(monkeypatch):
    raw = VisionResult(content='{"fields":[]}', model="mock", prompt_tokens=20, completion_tokens=5)
    monkeypatch.setattr(benchmark.LiteLLMVisionProvider, "extract", AsyncMock(return_value=raw))
    monkeypatch.setattr(
        benchmark.litellm, "cost_per_token", lambda **kwargs: (_ for _ in ()).throw(KeyError("x"))
    )
    provider = benchmark.AuditedVision(model="ollama/mock")
    asyncio.run(provider.extract(b"synthetic", "campos"))
    assert provider.readings[0]["estimated_cost_usd"] is None
    assert "KeyError" in provider.readings[0]["cost_status"]


def test_usage_cost_aggregation_partial_and_empty():
    readings = [row()]
    readings[0]["vision"] = [
        {"result": {"prompt_tokens": 10, "completion_tokens": 5}, "estimated_cost_usd": 0.001},
        {"result": {"prompt_tokens": 10, "completion_tokens": 5}, "estimated_cost_usd": None},
    ]
    score = benchmark.metrics([case()], readings)
    assert score["usage"]["prompt_tokens"] == 20
    assert score["usage"]["estimated_cost_usd"] == pytest.approx(0.001)
    assert "parcial" in score["usage"]["cost_status"]
    score = benchmark.metrics([case()], [row()])
    assert score["usage"]["calls"] == 0
    assert score["usage"]["estimated_cost_usd"] == 0.0


def test_ocr_audit_preserves_words(monkeypatch):
    monkeypatch.setattr(
        benchmark.RapidOcrProvider, "read", AsyncMock(return_value=OcrResult(engine="mock"))
    )
    provider = benchmark.AuditedOcr()
    asyncio.run(provider.read(b"synthetic"))
    assert provider.readings[0]["result"] == {"engine": "mock", "words": []}


def test_remote_provider_uses_mock_without_network(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(benchmark.settings, "VISION_ALLOW_REMOTE", True)
    mock = MockVisionProvider(fields={"fields": []})
    monkeypatch.setattr(benchmark.LiteLLMVisionProvider, "extract", mock.extract)
    agent = benchmark.build_agent("ocr+vlm-remoto", "openrouter/mock", None, 600)
    result = asyncio.run(agent.vision.extract(b"synthetic", "campos"))
    assert json.loads(result.content) == {"fields": []}
    assert agent.vision.is_remote


def test_provider_failure_audited(monkeypatch):
    monkeypatch.setattr(
        benchmark.LiteLLMVisionProvider, "extract", AsyncMock(side_effect=TimeoutError)
    )
    provider = benchmark.AuditedVision(model="ollama/mock")
    with pytest.raises(TimeoutError):
        asyncio.run(provider.extract(b"synthetic", "campos"))
    assert provider.readings[0]["error_type"] == "TimeoutError"


def test_runner_real_agent_checkpoints_and_failure(tmp_path, monkeypatch):
    data = benchmark.load_dataset()
    data["cases"] = data["cases"][:1]
    monkeypatch.setattr(benchmark, "load_dataset", lambda: data)
    monkeypatch.setattr(benchmark, "provenance", lambda: {"manifest_sha256": "test"})
    monkeypatch.setattr(
        benchmark.RapidOcrProvider, "read", AsyncMock(side_effect=RuntimeError("sem motor"))
    )
    output = tmp_path / "run"
    asyncio.run(benchmark.run(output, "ocr"))
    metadata = json.loads((output / "run.json").read_text())
    readings = json.loads((output / "readings.json").read_text())
    assert metadata["status"] == "completed"
    assert metadata["completed_documents"] == 1
    assert metadata["summary"]["calibration"]["technical_failures"] == 1
    assert metadata["summary"]["calibration"]["correct_documents"] == 0
    assert readings[0]["ocr"][0]["error_type"] == "RuntimeError"
    assert readings[0]["trace"]["status"] == "failed"
    with pytest.raises(ValueError, match="já existe"):
        asyncio.run(benchmark.run(output, "ocr"))
