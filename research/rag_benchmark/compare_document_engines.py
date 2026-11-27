"""Comparação auditável dos motores no agente real, somente com insumos sintéticos."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "research"))

dataset_module = importlib.import_module("rag_benchmark.document_dataset")
MANIFEST, load_dataset = dataset_module.MANIFEST, dataset_module.load_dataset
matched_rows = importlib.import_module("rag_benchmark.document_evaluation").matched_rows
LiteLLMVisionProvider = importlib.import_module(
    "app.clients.litellm_vision_provider"
).LiteLLMVisionProvider
RapidOcrProvider = importlib.import_module("app.clients.rapidocr_provider").RapidOcrProvider
settings = importlib.import_module("app.core.config").settings
document_module = importlib.import_module("app.services.agents.document")
DocumentAgent, DocumentContext = document_module.DocumentAgent, document_module.DocumentContext
litellm = importlib.import_module("litellm")

ENGINES = ("ocr", "ocr+vlm-local", "ocr+vlm-remoto")
TECHNICAL_CODES = {
    "OCR_TIMEOUT",
    "OCR_UNAVAILABLE",
    "VISION_UNAVAILABLE",
    "INVALID_VISION_OUTPUT",
    "VISION_REMOTE_BLOCKED",
    "VISION_PRIVACY_BLOCKED",
    "DOCUMENT_PROCESSING_FAILED",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SyntheticSanitizer:
    def sanitize(self, image: bytes) -> bytes:
        return image


class AuditedOcr(RapidOcrProvider):
    def __init__(self):
        super().__init__()
        self.readings = []

    async def read(self, image: bytes):
        item = {"input_sha256": hashlib.sha256(image).hexdigest()}
        self.readings.append(item)
        try:
            result = await super().read(image)
            item["result"] = result.model_dump(mode="json")
            return result
        except BaseException as error:
            item["error_type"] = type(error).__name__
            raise


class AuditedVision(LiteLLMVisionProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.readings = []

    async def extract(self, image, instructions, schema=None):
        item = {"input_sha256": hashlib.sha256(image).hexdigest()}
        self.readings.append(item)
        try:
            result = await super().extract(image, instructions, schema)
            item["result"] = result.model_dump(mode="json")
            try:
                prompt_cost, completion_cost = litellm.cost_per_token(
                    model=self.model,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                )
                item["estimated_cost_usd"] = prompt_cost + completion_cost
                item["cost_status"] = "estimado pela tabela de preços do litellm"
            except Exception as error:
                item["estimated_cost_usd"] = None
                item["cost_status"] = (
                    f"indisponível: modelo sem preço na tabela do litellm ({type(error).__name__})"
                )
            return result
        except BaseException as error:
            item["error_type"] = type(error).__name__
            raise


def build_agent(engine: str, model: str | None, api_base: str | None, timeout: float):
    if engine not in ENGINES:
        raise ValueError("Motor inválido.")
    ocr = AuditedOcr()
    vision = None
    if engine != "ocr":
        remote = engine == "ocr+vlm-remoto"
        model = model or ("" if remote else "ollama/mistral-small3.2:24b")
        if remote and (
            not model.startswith("openrouter/")
            or not os.environ.get("OPENROUTER_API_KEY")
            or not settings.VISION_ALLOW_REMOTE
        ):
            raise ValueError(
                "Remoto exige modelo openrouter/, OPENROUTER_API_KEY e VISION_ALLOW_REMOTE=true."
            )
        if not remote and not model.startswith(("ollama/", "ollama_chat/")):
            raise ValueError("Motor local exige modelo Ollama.")
        vision = AuditedVision(
            model=model,
            api_base=api_base
            or ("https://openrouter.ai/api/v1" if remote else "http://127.0.0.1:11434"),
            api_key=os.environ.get("OPENROUTER_API_KEY") if remote else "",
            timeout=timeout,
        )
        if vision.is_remote != remote:
            raise ValueError("Endereço incompatível com a modalidade local/remota.")
    return DocumentAgent(ocr=ocr, vision=vision, sanitizer=SyntheticSanitizer(), timeout=timeout)


def metrics(cases: list[dict], readings: list[dict]) -> dict:
    by_id = {row["id"]: row for row in readings}
    if len(by_id) != len(readings) or not set(by_id) <= {case["id"] for case in cases}:
        raise ValueError("IDs inválidos nas leituras.")
    totals = dict.fromkeys(
        (
            "correct_fields",
            "recoverable_fields",
            "wrong_fields",
            "missing_fields",
            "invented_fields",
            "correct_documents",
            "technical_failures",
            "illegible_documents",
            "safe_abstentions",
            "false_accepts",
        ),
        0,
    )
    per_field = {
        key: {"correct": 0, "expected": 0}
        for key in ("amount", "date", "counterparty", "total", "due_date", "bank")
    }
    latencies = []
    prompt_tokens = completion_tokens = calls = 0
    for case in cases:
        row = by_id.get(case["id"])
        if row is None:
            continue
        doc = row.get("document")
        failed = bool(row.get("technical_failures")) or doc is None
        totals["technical_failures"] += failed
        expected = case["recoverable_fields"]
        actual = {field["key"]: field["value"] for field in doc["fields"]} if doc else {}
        totals["recoverable_fields"] += len(expected)
        totals["invented_fields"] += len(actual.keys() - expected.keys())
        for key, value in expected.items():
            score = per_field.setdefault(key, {"correct": 0, "expected": 0})
            score["expected"] += 1
            correct = not failed and actual.get(key) == value
            score["correct"] += correct
            totals["correct_fields"] += correct
            totals["missing_fields"] += key not in actual
            totals["wrong_fields"] += key in actual and actual[key] != value
        bad = case["expected_quality"] == "illegible"
        safe = bool(
            not failed and doc and doc["abstained"] and not actual and not doc["transactions"]
        )
        totals["illegible_documents"] += bad
        totals["safe_abstentions"] += bad and safe
        totals["false_accepts"] += bool(
            bad and doc and (not doc["abstained"] or actual or doc["transactions"])
        )
        rows = doc["transactions"] if doc else []
        reference = case["recoverable_transactions"]
        exact = actual == expected and matched_rows(reference, rows) == len(reference) == len(rows)
        totals["correct_documents"] += bool(
            not failed and ((bad and safe) or (not bad and doc and not doc["abstained"] and exact))
        )
        latencies.append(row["latency_ms"])
        for call in row.get("vision", []):
            calls += 1
            usage = call.get("result", {})
            prompt_tokens += usage.get("prompt_tokens", 0)
            completion_tokens += usage.get("completion_tokens", 0)
    known_costs = [
        call["estimated_cost_usd"]
        for row in readings
        for call in row.get("vision", [])
        if call.get("estimated_cost_usd") is not None
    ]
    total_cost = sum(known_costs) if known_costs else (0.0 if calls == 0 else None)
    if calls and len(known_costs) < calls:
        cost_status = f"parcial: {calls - len(known_costs)} chamadas sem preço na tabela do litellm"
    else:
        cost_status = "sem chamadas de visão" if calls == 0 else "estimado pelo litellm"
    for score in per_field.values():
        score["accuracy"] = score["correct"] / score["expected"] if score["expected"] else None
    return {
        "documents": len(cases),
        "completed_documents": len(readings),
        **totals,
        "per_field": per_field,
        "field_accuracy": totals["correct_fields"] / totals["recoverable_fields"]
        if totals["recoverable_fields"]
        else None,
        "document_accuracy": totals["correct_documents"] / len(cases) if cases else None,
        "safe_abstention_rate": totals["safe_abstentions"] / totals["illegible_documents"]
        if totals["illegible_documents"]
        else None,
        "latency_ms": {
            "mean": statistics.mean(latencies) if latencies else None,
            "p95": sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
        },
        "usage": {
            "calls": calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": total_cost,
            "cost_status": cost_status,
        },
    }


def summarize(cases, readings):
    def subset(selected):
        ids = {case["id"] for case in selected}
        return metrics(selected, [row for row in readings if row["id"] in ids])

    return {
        split: {
            **subset([case for case in cases if case["split"] == split]),
            "by_degradation": {
                name: subset(
                    [
                        case
                        for case in cases
                        if case["split"] == split
                        and f"{case['degradation']['type']}:{case['degradation']['level']}" == name
                    ]
                )
                for name in sorted(
                    {
                        f"{case['degradation']['type']}:{case['degradation']['level']}"
                        for case in cases
                        if case["split"] == split
                    }
                )
            },
        }
        for split in ("calibration", "validation")
    }


def provenance():
    sources = [
        Path(__file__),
        ROOT / "research/rag_benchmark/document_dataset.py",
        ROOT / "research/rag_benchmark/document_evaluation.py",
    ]
    sources += sorted((ROOT / "api/app/services").glob("document*.py"))
    sources += [
        ROOT / path
        for path in (
            "api/app/services/agents/document.py",
            "api/app/services/image_quality.py",
            "api/app/clients/rapidocr_provider.py",
            "api/app/clients/litellm_vision_provider.py",
            "api/app/models/vision_provider.py",
            "api/app/domain/documents.py",
        )
    ]
    packages = {}
    for name in ("pillow", "numpy", "pypdfium2", "rapidocr-onnxruntime", "onnxruntime", "litellm"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "indisponível"
    return {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "manifest_sha256": digest(MANIFEST),
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in sources},
    }


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


async def run(output: Path, engine: str, model=None, api_base=None, timeout=600):
    if output.exists():
        raise ValueError(
            "Execução já existe; escolha outro RUN. Checkpoints existentes não são sobrescritos."
        )
    data = load_dataset()
    if data.get("synthetic_only") is not True:
        raise ValueError("Somente dados sintéticos são permitidos.")
    agent = build_agent(engine, model, api_base, timeout)
    metadata = {
        **provenance(),
        "created_at": datetime.now(UTC).isoformat(),
        "engine": engine,
        "model": agent.vision.model if agent.vision else None,
        "api_base": agent.vision.api_base if agent.vision else None,
        "timeout_seconds": timeout,
        "status": "running",
        "synthetic_only": True,
        "sanitizer": "identidade exclusivamente para os insumos sintéticos validados por manifesto",
        "threshold_policy": "constantes do app congeladas; nenhum ajuste nos dois conjuntos",
        "limitations": [
            "Sem revisão humana cega; documentos sintéticos.",
            "Inventados: chaves sem suporte recuperável; valores errados em contador separado.",
            "Custo estimado pela tabela do litellm quando há preço do modelo; senão nulo.",
            "Falhas técnicas não contam como acerto nem abstenção correta.",
        ],
    }
    readings = []
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "run.json", metadata)
    atomic_json(output / "readings.json", readings)
    for case in data["cases"]:
        agent.ocr.readings = []
        if agent.vision:
            agent.vision.readings = []
        started = time.perf_counter()
        row = {
            "id": case["id"],
            "input_sha256": digest(ROOT / case["path"]),
            "split": case["split"],
            "degradation": case["degradation"],
        }
        try:
            ctx = DocumentContext(
                content=(ROOT / case["path"]).read_bytes(), media_type=case["media_type"]
            )
            step = await agent.run(ctx)
            row["trace"] = step.model_dump(mode="json")
            row["document"] = ctx.result.model_dump(mode="json") if ctx.result else None
            codes = {issue.code for issue in ctx.result.issues} if ctx.result else set()
            if step.status == "failed":
                codes.add(step.detail.get("code", "DOCUMENT_PROCESSING_FAILED"))
            row["technical_failures"] = sorted(
                codes & TECHNICAL_CODES
                | ({"DOCUMENT_PROCESSING_FAILED"} if ctx.result is None else set())
            )
        except Exception as error:
            row.update(document=None, technical_failures=[type(error).__name__])
        row.update(
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            ocr=agent.ocr.readings,
            vision=agent.vision.readings if agent.vision else [],
        )
        if any("error_type" in call for call in row["ocr"] + row["vision"]):
            row["technical_failures"] = sorted(
                set(row["technical_failures"]) | {"PROVIDER_CALL_FAILED"}
            )
        readings.append(row)
        atomic_json(output / "readings.json", readings)
        metadata.update(
            completed_documents=len(readings), summary=summarize(data["cases"], readings)
        )
        atomic_json(output / "run.json", metadata)
        print(f"{case['id']} {row['latency_ms']} ms falhas={row['technical_failures']}", flush=True)
    metadata.update(status="completed", finished_at=datetime.now(UTC).isoformat())
    atomic_json(output / "run.json", metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--engine", choices=ENGINES, required=True)
    parser.add_argument("--model")
    parser.add_argument("--api-base")
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    if Path(args.run).name != args.run or args.run in {".", ".."} or args.timeout <= 0:
        parser.error("RUN deve ser um nome simples e timeout deve ser positivo.")
    asyncio.run(
        run(
            ROOT / "research/rag_benchmark/results/documents" / args.run,
            args.engine,
            args.model,
            args.api_base,
            args.timeout,
        )
    )


if __name__ == "__main__":
    main()
