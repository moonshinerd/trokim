import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from chat_dados import MANIFEST, ROOT, load_library, validate

from app.clients.litellm_provider import LiteLLMProvider
from app.core.config import settings
from app.domain.agents import FinancialFilters
from app.services.agent_query_service import AgentQueryService
from app.services.agents.analysis import AnalysisAgent
from app.services.agents.communication import CommunicationAgent
from app.services.agents.orchestrator import Orchestrator
from app.services.agents.research import ResearchAgent
from app.services.agents.validation import ValidationAgent
from app.services.financial_number_validation import check_financial_numbers
from app.services.number_format import canonicalize_number

RESULTS = Path(__file__).parent / "results/chat_dados"


class RecordingProvider:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    async def generate(self, prompt, **kwargs):
        started = time.perf_counter()
        try:
            response = await self.provider.generate(prompt, **kwargs)
        except Exception as exc:
            self.calls.append(
                {
                    "error_type": type(exc).__name__,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                }
            )
            raise
        self.calls.append(
            {
                "content": response.content,
                "model": response.model,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }
        )
        return response


class RecordingValidation(ValidationAgent):
    def __init__(self):
        super().__init__()
        self.contexts = []

    async def run(self, ctx):
        step = await super().run(ctx)
        self.contexts.append(
            {
                "draft": ctx.draft_answer,
                "notes": list(ctx.assumptions),
                "issues": [i.model_dump(mode="json") for i in ctx.issues],
                "step": step.model_dump(mode="json"),
            }
        )
        return step


def contains_value(text: str, expected: dict) -> bool:
    pattern = (
        r"(?:R\$\s*(?P<prefix>[+−–-]?\s*\d+(?:[.,]\d+)*))|"
        r"(?P<suffix>[+−–-]?\s*\d+(?:[.,]\d+)*)\s*BRL\b"
    )
    for match in re.finditer(pattern, text):
        token = (match["prefix"] or match["suffix"]).replace(" ", "")
        token = token.translate(str.maketrans({"−": "-", "–": "-"}))
        if abs(float(canonicalize_number(token)) - expected["value"]) < 0.005:
            return True
    return False


def evaluate(question, response, calls, contexts):
    notes = contexts[-1]["notes"] if contexts else [response.answer]
    calculations = {c.key: c for c in response.calculations}
    # Cálculo determinístico certo, independentemente de a resposta ter sido entregue.
    computed = [
        bool(
            calculations.get(expected["key"])
            and calculations[expected["key"]].unit == expected["unit"]
            and abs(float(calculations[expected["key"]].value) - expected["value"]) < 0.005
        )
        for expected in question["expected"]
    ]
    hits = []
    for expected in question["expected"]:
        actual = calculations.get(expected["key"])
        hits.append(
            bool(
                actual
                and actual.unit == expected["unit"]
                and abs(float(actual.value) - expected["value"]) < 0.005
                and contains_value(response.answer, expected)
                and response.status == "answered"
            )
        )
    raw_issues = [
        check_financial_numbers(call["content"], response.calculations, notes)
        for call in calls
        if "content" in call
    ]
    final_issues = check_financial_numbers(response.answer, response.calculations, notes)
    validation_codes = [issue["code"] for context in contexts for issue in context["issues"]]
    expected_behavior = question["behavior"]
    clarification = bool(re.search(r"informe|qual|quais|quer|esclare", response.answer, re.I))
    missing = bool(
        re.search(r"não há|não identifiquei|importe|nenhuma conta", response.answer, re.I)
    )
    abstention_ok = (
        response.status == "abstained"
        and not response.calculations
        and not calls
        and (clarification if expected_behavior == "clarify" else missing)
    )
    # Rejeição do Validation é decisão de segurança, não falha técnica: só conta como técnica
    # a chamada ao modelo que falhou ou um passo que não seja a validação.
    technical = any("error_type" in c for c in calls) or any(
        s.status == "failed" and s.agent != "validation" for s in response.steps
    )
    return {
        "numeric_expected": len(hits),
        "calculation_correct": sum(computed),
        "numeric_correct": sum(hits),
        "rejected_by_validation": response.status == "rejected",
        "numeric_case_correct": bool(hits) and all(hits) and not technical,
        "raw_model_calls": len(raw_issues),
        "raw_model_calls_with_invented_numbers": sum(bool(i) for i in raw_issues),
        "raw_model_invented_numbers": sum(map(len, raw_issues)),
        "final_invented_numbers": len(final_issues),
        "abstention_expected": expected_behavior != "answer",
        "abstention_correct": expected_behavior != "answer" and abstention_ok and not technical,
        "validation_number_not_supported": validation_codes.count("NUMBER_NOT_SUPPORTED"),
        "validation_calculation_missing": validation_codes.count("CALCULATION_MISSING"),
        "validation_blocked": any(c["step"]["status"] != "ok" for c in contexts),
        "safe_fallbacks": sum(
            s.detail.get("draft_guard") == "safe_fallback" for s in response.steps
        ),
        "technical_failure": technical,
    }


def reserve_run(run: str, root: Path = RESULTS) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run):
        raise ValueError("RUN inválido.")
    target = root / run
    target.mkdir(parents=True, exist_ok=False)
    return target


def provenance(model, api_base):
    paths = list((ROOT / "api/app").rglob("*.py")) + list((ROOT / "api/app/prompts").glob("*.txt"))
    return {
        "started_at": datetime.now(UTC).isoformat(),
        "model": model,
        "api_base": api_base,
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
        ),
        "python": platform.python_version(),
        "packages": {
            name: importlib.metadata.version(name) for name in ("litellm", "pydantic", "jsonschema")
        },
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)
        },
        "parameters": {
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "timeout": 180,
        },
        "protocol": (
            "AgentQueryService.run; mesmos agentes de POST /v1/agents/ask; "
            "sem HTTP e sem RAG nas consultas factuais"
        ),
        "limitations": [
            "Sem revisão humana cega.",
            "Acerto final inclui fallback determinístico e não mede aritmética do modelo.",
            "Rascunhos auditados pela política do produto, não por avaliador independente.",
            "Gabarito independente da intenção; parcelas futuras somadas por CalculationService.",
            "Relógio real registrado; expectativas de dívidas independem da janela relativa.",
        ],
    }


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def run_benchmark(run, model, api_base):
    questions = validate()
    target = reserve_run(run)
    record = provenance(model, api_base)
    record.update(run=run, status="running")
    save(target / "run.json", record)
    readings = []
    provider = RecordingProvider(LiteLLMProvider(model=model, api_base=api_base, timeout=180))
    for question in questions:
        provider.calls = []
        validation = RecordingValidation()
        orchestrator = Orchestrator(
            research=ResearchAgent(),
            analysis=AnalysisAgent(),
            communication=CommunicationAgent(llm_provider=provider),
            validation=validation,
        )
        started = time.perf_counter()
        try:
            response = await AgentQueryService(orchestrator).run(
                question["question"],
                library=load_library(),
                filters=FinancialFilters(**question["filters"]),
            )
            reading = {
                "id": question["id"],
                "response": response.model_dump(mode="json"),
                "metrics": evaluate(question, response, provider.calls, validation.contexts),
            }
        except Exception as exc:
            reading = {
                "id": question["id"],
                "error_type": type(exc).__name__,
                "metrics": {
                    "technical_failure": True,
                    "numeric_expected": len(question["expected"]),
                    "numeric_correct": 0,
                    "abstention_expected": question["behavior"] != "answer",
                    "abstention_correct": False,
                },
            }
        reading.update(
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            model_calls=provider.calls,
            validation_contexts=validation.contexts,
        )
        readings.append(reading)
        save(target / "readings.json", readings)
        print(
            f"{question['id']}: {reading.get('response', {}).get('status', 'technical_failure')}",
            flush=True,
        )
    counts = Counter()
    for reading in readings:
        counts.update(reading["metrics"])
    record.update(
        status="completed",
        finished_at=datetime.now(UTC).isoformat(),
        scenarios=len(readings),
        metrics=dict(counts),
        statuses=dict(
            Counter(r.get("response", {}).get("status", "technical_failure") for r in readings)
        ),
    )
    save(target / "run.json", record)
    print(json.dumps(record["metrics"], ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", "ollama/qwen2.5:1.5b"))
    parser.add_argument("--api-base", default=os.getenv("LLM_API_BASE", "http://127.0.0.1:11434"))
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.run, args.model, args.api_base))


if __name__ == "__main__":
    main()
