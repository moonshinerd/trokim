"""Peças comuns do benchmark multiagente (#60), usadas por ``run_comparison.py --multiagent``
(30 casos da Semana 3) e por ``run_multiagent.py`` (20 cenários do gabarito).

- Execução com os agentes reais, em processo, sobre o corpus unificado de 22 fontes, com o
  mesmo top-k, limiar e alpha do Trokim estruturado e o mesmo teto de 300 tokens das outras
  abordagens.
- Preservação, por tentativa, da resposta original do modelo (``llm_responses``) e do rascunho
  enviado ao Validation (``drafts``): o Communication pode trocar o texto do modelo por um
  rascunho seguro, e a auditoria precisa ver os dois.
- Falha do modelo ou de um agente fica registrada (``model_failed``) e nunca conta como recusa
  segura.
- Registro da execução (``run.json``) e formulário de auditoria pendente, sem sobrescrever
  nada nem confirmar sinalizações automaticamente.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import time
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from multiagent import MANIFEST, QUESTIONS, SCHEMA, manifest

from app.domain.agents import AgentName, AgentStep, StepStatus
from app.domain.models import Transaction
from app.services.agents.analysis import AnalysisAgent
from app.services.agents.communication import CommunicationAgent
from app.services.agents.orchestrator import Orchestrator
from app.services.agents.research import ResearchAgent
from app.services.agents.validation import ValidationAgent
from app.services.rag_service import RAGService

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research/rag_benchmark/results"
RUN_ID = re.compile(r"\d{4}-\d{2}-\d{2}-[a-zA-Z0-9_.-]+")
# Mesmo orçamento de geração das três abordagens da Semana 3.
MAX_TOKENS = 300
TOP_K, THRESHOLD, ALPHA = 3, 0.15, 0.3


class ComparisonRAG:
    """Research sobre o corpus unificado, com a política de escopo e a recuperação do Trokim
    estruturado: a diferença medida é só a do fluxo multiagente."""

    top_k = TOP_K
    threshold = THRESHOLD
    is_outside_scope = staticmethod(RAGService.is_outside_scope)

    def __init__(self, retriever: Any) -> None:
        self.retriever = retriever

    def retrieve_evidence(self, query: str) -> list:
        return self.retriever.retrieve_hybrid(
            query, top_k=self.top_k, threshold=self.threshold, alpha=ALPHA
        )


class RecordingLLM:
    """Guarda a resposta original do provedor em cada tentativa, antes de qualquer troca."""

    def __init__(self, provider: Any) -> None:
        self.provider = provider
        self.responses: list[dict[str, Any]] = []

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        response = await self.provider.generate(prompt, **kwargs)
        self.responses.append(response.model_dump(mode="json"))
        return response


class RecordedCommunication:
    """Guarda o rascunho que segue para o Validation em cada tentativa."""

    name = AgentName.COMMUNICATION

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.drafts: list[dict[str, Any]] = []

    async def run(self, ctx: Any) -> AgentStep:
        step = await self.delegate.run(ctx)
        self.drafts.append(
            {
                "answer": ctx.draft_answer,
                "abstain_reason": ctx.abstain_reason,
                "calculations": [c.model_dump(mode="json") for c in ctx.calculations],
                "evidence_ids": [e.id for e in ctx.evidences],
            }
        )
        return step


class FixtureResearch:
    """Ensaio injetado: deixa o fluxo seguir sem recuperação."""

    name = AgentName.RESEARCH

    async def run(self, ctx: Any) -> AgentStep:
        return AgentStep(agent=self.name, status=StepStatus.OK, summary="Ensaio controlado.")


class FixtureCommunication:
    """Ensaio injetado: repete o rascunho inválido do gabarito; nunca entra no ensaio livre."""

    name = AgentName.COMMUNICATION

    def __init__(self, fixture: dict[str, Any]) -> None:
        self.fixture = fixture

    async def run(self, ctx: Any) -> AgentStep:
        ctx.draft_answer = self.fixture["draft_answer"]
        ctx.abstain_reason = self.fixture["abstain_reason"]
        return AgentStep(agent=self.name, status=StepStatus.OK, summary="Rascunho adversarial.")


def legacy_transactions(case: dict[str, Any]) -> list[Transaction]:
    """C29: lançamentos sintéticos com os mesmos totais que as outras abordagens recebem no
    prompt. C30 e os demais casos continuam sem lançamentos."""
    if case.get("calculation_fixture") != "resumo_centavos":
        return []
    from comparison import calculation_results

    summary = calculation_results("resumo_centavos")
    return [
        Transaction(
            id=f"SINTETICO-COMPARACAO-{kind}",
            account_id="TESTE-SINTETICO-COMPARACAO",
            description="Totais fictícios do gerador comparativo",
            date=date(2026, 11, 1),
            amount=summary[key],
            type=kind,
        )
        for kind, key in (("credit", "total_income"), ("debit", "total_expenses"))
    ]


def model_failed(steps: list[dict[str, Any]]) -> bool:
    """Algum agente falhou por erro (o modelo sem resposta, por exemplo), e não por reprovação
    do Validation."""
    return any(
        s["status"] == "failed" and (s["agent"] != "validation" or "error" in s.get("detail", {}))
        for s in steps
    )


async def execute_multiagent(
    question: str,
    llm: Any,
    evidence_source: Any,
    *,
    temperature: float = 0.1,
    transactions: list[Transaction] | None = None,
    max_tokens: int = MAX_TOKENS,
) -> dict[str, Any]:
    """Uma pergunta pelo orquestrador real, com a trilha completa e o material de auditoria."""
    recording = RecordingLLM(llm)
    communication = RecordedCommunication(
        CommunicationAgent(recording, temperature=temperature, max_tokens=max_tokens)
    )
    orchestrator = Orchestrator(
        ResearchAgent(evidence_source), AnalysisAgent(), communication, ValidationAgent()
    )
    t0 = time.perf_counter()
    response = await orchestrator.run(question, transactions or [])
    latency = round((time.perf_counter() - t0) * 1000, 2)
    data = response.model_dump(mode="json")
    steps = [
        {k: s[k] for k in ("agent", "status", "duration_ms", "summary", "detail")}
        for s in data["steps"]
    ]
    status = data["status"]
    return {
        "answer": data["answer"].strip(),
        "status": status,
        "answered": status == "answered",
        "abstained": status != "answered",
        "latency_ms": latency,
        "model": data.get("model"),
        "retrieved_chunks": [e["id"] for e in data["evidences"]],
        "evidences": [e["document_title"] for e in data["evidences"]],
        "calculations": data["calculations"],
        "validation_issues": [
            {"code": i["code"], "severity": i["severity"], "message": i["message"]}
            for i in data["validation_issues"]
        ],
        "steps": steps,
        "model_failed": model_failed(steps),
        "drafts": communication.drafts,
        "llm_responses": recording.responses,
    }


async def execute_injected(case: dict[str, Any], ledger: list[Transaction]) -> dict[str, Any]:
    """Ensaio controlado: Research e Communication fixos; Analysis e Validation reais."""
    fixture = case["validation_fixture"]
    communication = RecordedCommunication(FixtureCommunication(fixture))
    t0 = time.perf_counter()
    response = await Orchestrator(
        FixtureResearch(), AnalysisAgent(), communication, ValidationAgent()
    ).run(case["question"], ledger if fixture["use_ledger"] else [])
    data = response.model_dump(mode="json")
    return {
        "status": data["status"],
        "answer": data["answer"].strip(),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "validation_issues": [
            {"code": i["code"], "severity": i["severity"], "message": i["message"]}
            for i in data["validation_issues"]
        ],
        "steps": [
            {k: s[k] for k in ("agent", "status", "duration_ms", "summary")} for s in data["steps"]
        ],
        "drafts": communication.drafts,
        "draft_retained": data["answer"].strip() != fixture["draft_answer"],
    }


def load_multiagent_cases() -> list[dict[str, Any]]:
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(data)
    if json.loads(MANIFEST.read_text(encoding="utf-8")) != manifest():
        raise ValueError("Manifesto multiagente divergente; revise os insumos.")
    return data["cases"]


_NUMBER = r"[-+]?\s*(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
_UNIT_PATTERN = {
    "BRL": rf"(?:R\$\s*({_NUMBER})(?!\d|[.,]\d)|(?<![\w.,])({_NUMBER})\s*(?:BRL|reais)\b)",
    "%": rf"(?<![\w.,\[])({_NUMBER})\s*%",
    "meses": rf"(?<![\w.,\[])({_NUMBER})\s*(?:meses|mês)\b",
}
# Percentual aceita o arredondamento para uma casa (38,66% → 38,7%).
_TOLERANCE = {"BRL": 0.005, "%": 0.051, "meses": 0.0}


def numeric_matches(answer: str, expected: dict[str, Any]) -> bool:
    """O valor esperado aparece com a unidade e o sinal certos.

    A presença no texto não prova que o valor foi atribuído à grandeza certa; esse vínculo
    fica para a revisão humana.
    """
    unit = expected["unit"]
    for match in re.finditer(_UNIT_PATTERN[unit], answer, re.IGNORECASE):
        raw = next(g for g in match.groups() if g is not None).replace(" ", "")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})+", raw):
            raw = raw.replace(".", "")
        if math.isclose(float(raw), expected["value"], rel_tol=0, abs_tol=_TOLERANCE[unit]):
            return True
    return False


def write_audit_template(path: Path, rows: list[dict[str, Any]]) -> None:
    """Formulário de revisão humana: começa sem revisor e sem nenhuma confirmação."""
    if path.exists():
        raise FileExistsError(f"{path} já existe; não sobrescrever decisões humanas.")
    for row in rows:
        row.setdefault("confirmed", None)
        row.setdefault("notes", "")
    path.write_text(
        json.dumps(
            {"status": "pendente", "reviewer": None, "cases": rows}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )


def comparison_audit_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Sinalizados de qualquer abordagem e os casos da hipótese (C27, C29, C30)."""
    rows = []
    for method, data in report["methods"].items():
        for case in data["case_details"]:
            flagged = bool(case["factual_inconsistencies"])
            if flagged or case["id"] in {"C27", "C29", "C30"}:
                rows.append({"method": method, "id": case["id"], "flagged": flagged})
    return rows


def scenario_audit_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Armadilhas, bloqueios, falhas do modelo e números ausentes nos 20 cenários."""
    rows = []
    for case in report["free"]["case_details"]:
        missing = case["numbers_reproduced"] < case["numbers_expected"]
        if case["category"] == "armadilha" or case["blocked"] or case["model_failed"] or missing:
            rows.append(
                {
                    "method": "multiagente",
                    "id": case["id"],
                    "flagged": case["needs_review"] or missing,
                    "block_correct": None if case["blocked"] else "não se aplica",
                }
            )
    return rows


def git_commit() -> tuple[str, bool]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True
    ).strip()
    return commit, bool(dirty)


def check_new_run(run_id: str, directory: Path) -> None:
    """Identificador AAAA-MM-DD-..., pasta nova: uma execução publicada nunca é sobrescrita."""
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("RUN deve ser AAAA-MM-DD-<modelo>, com letras, números, ponto ou hífen.")
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(
            f"{directory} já tem uma execução; use outro identificador para preservar o histórico."
        )


def write_run_registry(
    run_id: str,
    report: dict[str, Any],
    *,
    model: str,
    provider: str,
    temperature: float,
    notes: str = "",
) -> Path:
    """Cria ``run.json`` a partir do relatório gerado (sem digitar números)."""
    directory = RESULTS / "comparison" / run_id
    commit, dirty = git_commit()

    def rel(name: str) -> str:
        return str((directory / name).relative_to(ROOT))

    run = {
        "schema_version": 1,
        "run_id": run_id,
        "date": run_id[:10],
        "reference_commit": commit,
        "working_tree_dirty": dirty,
        "issue": "#60",
        "model": model,
        "provider": provider,
        "temperature": temperature,
        "top_k": TOP_K,
        "max_tokens": MAX_TOKENS,
        "repetitions": 1,
        "cases": report["case_count"],
        "corpus": "20 documentos históricos + suplemento exclusivo da comparação (22 fontes)",
        "raw_responses": rel("comparison_results.json"),
        "report": rel("comparison_report.md"),
        "audit": None,
        "audit_pending": rel("audit_pending.json"),
        "source_of_numbers": (
            "comparison_report.json gerado pelo runner; sinalizações sem confirmação humana"
        ),
        "approaches": {
            key: {
                "label": m["label"],
                "f1_tokens": round(m["token_f1"], 4),
                "concept_coverage": round(m["concept_recall"], 4),
                "inconsistency_rate": round(m["factual_inconsistency_rate"], 4),
                "abstention_f1": round(m["abstention_f1"], 4),
                "latency_ms": round(m["latency_mean_ms"]),
                "audit": None,
            }
            for key, m in report["methods"].items()
        },
        "notes": notes
        or "Uma execução; sinalizações e bloqueios aguardam revisão humana (audit_pending.json).",
    }
    path = directory / "run.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(run, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return path


def scenario_summary(run_id: str, report: dict[str, Any]) -> dict[str, Any]:
    free = report["free"]
    return {
        "report": f"research/rag_benchmark/results/multiagent/{run_id}/multiagent_report.md",
        "cases": report["case_count"],
        "status_ok": free["status_ok"],
        "numbers_expected": free["numbers_expected"],
        "numbers_reproduced": free["numbers_reproduced"],
        "validation_block_rate": round(free["validation_block_rate"], 4),
        "traps_safe": free["traps_safe"],
        "injected_blocked": report["injected"]["blocked_with_expected_code"],
        "latency_mean_ms": free["latency_mean_ms"],
    }


def add_scenarios_to_registry(
    run_id: str, report: dict[str, Any], *, replace: bool = False
) -> bool:
    """Acrescenta o resumo dos cenários ao ``run.json`` da mesma execução, se ele existir.

    ``replace`` só serve para a reavaliação (mesmas respostas brutas, avaliador novo).
    """
    path = RESULTS / "comparison" / run_id / "run.json"
    if not path.exists():
        return False
    run = json.loads(path.read_text(encoding="utf-8"))
    if "multiagent_scenarios" in run and not replace:
        raise FileExistsError(f"{path} já tem os cenários; use outro identificador.")
    run["multiagent_scenarios"] = scenario_summary(run_id, report)
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True
