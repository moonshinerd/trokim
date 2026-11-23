"""Calibração sintética do porteiro e ensaio opcional com RapidOCR real (#88/#90).

Nunca alimenta o agente com rótulos, campos esperados ou texto original.
Não substitui o comparador de motores da #98. Recusa sobrescrever uma execução.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "research"))

from rag_benchmark.document_dataset import MANIFEST, load_dataset  # noqa: E402

from app.clients.rapidocr_provider import RapidOcrProvider  # noqa: E402
from app.services import image_quality  # noqa: E402
from app.services.agents.document import DocumentAgent, DocumentContext  # noqa: E402
from app.services.document_reading import read_pages, render_pdf_page  # noqa: E402


def image_metrics(case: dict) -> dict:
    content = (ROOT / case["path"]).read_bytes()
    page = next(read_pages(content, case["media_type"]))
    image = page.image or render_pdf_page(content, 0)
    try:
        report = image_quality.assess_quality(image)
        return {
            "sharpness": report.sharpness,
            "min_side": min(image.size),
            "contrast": float(np.asarray(image.convert("L"), dtype=np.float64).std()),
            "resolution": list(image.size),
        }
    finally:
        image.close()


def rejected(metrics: dict, limits: dict) -> bool:
    return any(metrics[key] < limits[key] for key in limits)


def calibrate(cases: list[dict], metrics: dict[str, dict]) -> dict:
    """Busca só na calibração; empates preservam constantes atuais, sem olhar a validação."""
    if any(case["split"] != "calibration" for case in cases):
        raise ValueError("A calibração não pode receber casos de validação.")
    if not cases:
        raise ValueError("Calibração vazia.")
    defaults = {
        "min_side": image_quality.MIN_SIDE,
        "sharpness": image_quality.MIN_SHARPNESS,
        "contrast": image_quality.MIN_CONTRAST,
    }
    candidates = [defaults] + [
        {"min_side": side, "sharpness": sharp, "contrast": contrast}
        for side in (240, 320, 400)
        for sharp in (5.0, 10.0, 15.0, 25.0)
        for contrast in (6.0, 8.0, 12.0)
    ]

    def score(limits):
        false_accept = sum(
            not rejected(metrics[c["id"]], limits)
            for c in cases
            if c["expected_quality"] == "illegible"
        )
        false_reject = sum(
            rejected(metrics[c["id"]], limits)
            for c in cases
            if c["expected_quality"] != "illegible"
        )
        return false_accept, false_reject, sum(limits[k] != defaults[k] for k in limits)

    selected = min(candidates, key=score)
    return {
        "limits": selected,
        "calibration_ids": [c["id"] for c in cases],
        "objective": "falso aceite, falsa rejeição, mudanças dos limites (ordem lexicográfica)",
        "calibration_errors": list(score(selected)[:2]),
        "candidates": len(candidates),
    }


def summarize(cases: list[dict], readings: list[dict]) -> dict:
    """Acerto exato normalizado; campos omitidos contam no denominador recuperável."""
    truth = {case["id"]: case for case in cases}
    summary = {}
    for split in ("calibration", "validation"):
        rows = [row for row in readings if truth[row["id"]]["split"] == split]
        field_correct = field_total = unexpected = 0
        transaction_correct = transaction_total = unexpected_rows = 0
        illegible = abstentions = failures = 0
        gate_matrix = {
            "readable_accepted": 0,
            "readable_rejected": 0,
            "illegible_accepted": 0,
            "illegible_rejected": 0,
        }
        for row in rows:
            case = truth[row["id"]]
            bad = case["expected_quality"] == "illegible"
            gate_matrix[
                ("illegible" if bad else "readable")
                + ("_rejected" if row["gate_rejected"] else "_accepted")
            ] += 1
            if "document" not in row:
                continue
            doc = row["document"]
            failures += doc is None
            if bad:
                illegible += 1
                abstentions += bool(
                    doc and doc["abstained"] and not doc["fields"] and not doc["transactions"]
                )
            expected = case["recoverable_fields"]
            actual = {field["key"]: field["value"] for field in doc["fields"]} if doc else {}
            field_total += len(expected)
            field_correct += sum(actual.get(key) == value for key, value in expected.items())
            unexpected += sum(key not in expected for key in actual)
            expected_rows = case["recoverable_transactions"]
            actual_rows = doc["transactions"] if doc else []
            transaction_total += len(expected_rows)
            matched = set()
            for actual_row in actual_rows:
                for i, expected_row in enumerate(expected_rows):
                    if i not in matched and all(
                        str(actual_row[key]) == str(expected_row[key])
                        if key != "amount"
                        else actual_row[key] == float(expected_row[key])
                        for key in ("date", "description", "amount", "installment")
                    ):
                        matched.add(i)
                        break
                else:
                    unexpected_rows += 1
            transaction_correct += len(matched)
        summary[split] = {
            "documents": len(rows),
            "gate": gate_matrix,
            "correct_fields": field_correct,
            "recoverable_fields": field_total,
            "unexpected_fields": unexpected,
            "correct_transactions": transaction_correct,
            "recoverable_transactions": transaction_total,
            "unmatched_transactions": unexpected_rows,
            "illegible_documents": illegible,
            "safe_abstentions": abstentions,
            "technical_failures": failures,
        }
        if not any("document" in row for row in rows):
            for key in summary[split]:
                if key not in {"documents", "gate"}:
                    summary[split][key] = None
    return summary


class AuditedOcr(RapidOcrProvider):
    """Guarda leitura bruta apenas no runner, exclusivamente para estes dados sintéticos."""

    def __init__(self):
        super().__init__()
        self.readings = []

    async def read(self, image: bytes):
        result = await super().read(image)
        self.readings.append(result.model_dump(mode="json"))
        return result


async def run(output: Path, use_ocr: bool) -> None:
    if output.exists():
        raise ValueError("Execução já existe; escolha outro destino.")
    data = load_dataset()
    cases = data["cases"]
    metrics = {case["id"]: image_metrics(case) for case in cases}
    selection = calibrate([case for case in cases if case["split"] == "calibration"], metrics)
    # O agente usa as constantes publicadas; o relatório não instala limites silenciosamente.
    selected = selection["limits"]
    if selected != {
        "min_side": image_quality.MIN_SIDE,
        "sharpness": image_quality.MIN_SHARPNESS,
        "contrast": image_quality.MIN_CONTRAST,
    }:
        raise ValueError(
            "Publique os limites selecionados e repita o ensaio antes de avaliar a validação."
        )
    ocr = AuditedOcr() if use_ocr else None
    if ocr:
        ocr._load()  # Falha explicitamente antes de criar resultado quando o motor não existe.
    readings = []
    for case in cases:
        row = {
            "id": case["id"],
            "metrics": metrics[case["id"]],
            "gate_rejected": rejected(metrics[case["id"]], selected),
        }
        if ocr:
            ocr.readings = []
            ctx = DocumentContext(
                content=(ROOT / case["path"]).read_bytes(), media_type=case["media_type"]
            )
            started = time.perf_counter()
            step = await DocumentAgent(ocr=ocr, timeout=120).run(ctx)
            row.update(
                document=ctx.result.model_dump(mode="json") if ctx.result else None,
                trace=step.model_dump(mode="json"),
                ocr=ocr.readings,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        readings.append(row)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unavailable", True
    tracked_code = [
        "api/app/services/image_quality.py",
        "api/app/services/document_fields.py",
        "api/app/services/document_ocr.py",
        "api/app/services/agents/document.py",
        "api/app/clients/rapidocr_provider.py",
        "research/rag_benchmark/calibrate_documents.py",
    ]
    metadata = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": commit,
        "dirty": dirty,
        "mode": "rapidocr" if use_ocr else "quality_only",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["pillow", "numpy", "reportlab", "pypdfium2"]
            + (["rapidocr-onnxruntime", "onnxruntime"] if ocr else [])
        },
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in tracked_code
        },
        "ocr_confidence": image_quality.MIN_OCR_CONFIDENCE,
        "calibration": selection,
        "summary": summarize(cases, readings),
        "limitations": [
            "Dados sintéticos de desenvolvimento; sem revisão humana cega.",
            "Verificação separada por família; não é amostra de fotografias reais.",
            "A confiança OCR 0,80 é política conservadora; não probabilidade calibrada.",
            "Comparação de motores e meta de 90% pertencem à #98.",
        ],
    }
    output.mkdir(parents=True)
    (output / "run.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "readings.json").write_text(
        json.dumps(readings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata["summary"], ensure_ascii=False, indent=2))
    if use_ocr and any(
        group["technical_failures"] or group["illegible_documents"] != group["safe_abstentions"]
        for group in metadata["summary"].values()
    ):
        raise RuntimeError(
            "Ensaio falhou: erro técnico ou ilegível sem abstenção segura; veja leituras."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ocr", action="store_true", help="Exige o extra ocr; não usa mocks.")
    args = parser.parse_args()
    asyncio.run(run(args.output, args.ocr))


if __name__ == "__main__":
    main()
