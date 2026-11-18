"""Ensaio multiagente: perguntas livres e validação adversarial separadas (#60)."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import fmean

from eval_comparison import concept_recall, factual_inconsistencies
from jsonschema import Draft202012Validator
from multiagent import MANIFEST, QUESTIONS, SCHEMA, load_ledger, manifest

from app.domain.agents import AgentName, AgentStep, StepStatus
from app.domain.models import Transaction
from app.services.agents.analysis import AnalysisAgent
from app.services.agents.communication import CommunicationAgent
from app.services.agents.orchestrator import Orchestrator
from app.services.agents.research import ResearchAgent
from app.services.agents.validation import ValidationAgent
from app.services.rag_service import RAGService


class ComparisonRAG:
    """Mantém as 22 fontes, limiar e recuperação das abordagens de comparação."""

    top_k = 3
    threshold = 0.15
    is_outside_scope = staticmethod(RAGService.is_outside_scope)

    def __init__(self, retriever):
        self.retriever = retriever

    def retrieve_evidence(self, query):
        return self.retriever.retrieve_hybrid(
            query, top_k=self.top_k, threshold=self.threshold, alpha=0.3
        )


class ComparisonLLM:
    """Usa o mesmo orçamento de geração das três abordagens históricas."""

    def __init__(self, provider):
        self.provider = provider

    async def generate(self, prompt, **kwargs):
        if kwargs.get("max_tokens") is None:
            kwargs["max_tokens"] = 300
        return await self.provider.generate(prompt, **kwargs)


class RecordedCommunication:
    """Guarda os rascunhos do ensaio, inclusive o que a validação retém."""

    name = AgentName.COMMUNICATION

    def __init__(self, delegate):
        self.delegate = delegate
        self.drafts = []

    async def run(self, ctx):
        step = await self.delegate.run(ctx)
        self.drafts.append(
            {
                "answer": ctx.draft_answer,
                "calculations": [item.model_dump(mode="json") for item in ctx.calculations],
                "evidences": [item.model_dump(mode="json") for item in ctx.evidences],
                "abstain_reason": ctx.abstain_reason,
            }
        )
        return step


class FixtureResearch:
    """Permite que o ensaio controlado alcance a validação real."""

    name = AgentName.RESEARCH

    async def run(self, ctx):
        return AgentStep(agent=self.name, status=StepStatus.OK, summary="Ensaio controlado.")


class FixtureCommunication:
    """Repete uma violação conhecida; nunca participa da geração livre."""

    name = AgentName.COMMUNICATION

    def __init__(self, fixture):
        self.fixture = fixture

    async def run(self, ctx):
        ctx.draft_answer = self.fixture["draft_answer"]
        ctx.abstain_reason = self.fixture["abstain_reason"]
        return AgentStep(agent=self.name, status=StepStatus.OK, summary="Rascunho adversarial.")


def legacy_transactions(case):
    """Reconstrói totais do gerador histórico só quando existe resultado fornecido."""
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


async def execute_multiagent(case, llm, retriever, temperature=0.1, transactions=None):
    communication = RecordedCommunication(
        CommunicationAgent(ComparisonLLM(llm), temperature=temperature)
    )
    response = await Orchestrator(
        ResearchAgent(ComparisonRAG(retriever)), AnalysisAgent(), communication, ValidationAgent()
    ).run(
        case.get("query", case.get("question")),
        legacy_transactions(case) if transactions is None else transactions,
    )
    data = response.model_dump(mode="json")
    # Falha de infraestrutura não é recusa segura nem resultado experimental válido.
    if any(
        step["status"] == "failed" and (step["agent"] != "validation" or "error" in step["detail"])
        for step in data["steps"]
    ):
        raise RuntimeError(f"{case['id']}: falha de agente; execução incompleta.")
    data.update(
        latency_ms=data["total_ms"],
        answered=data["status"] == "answered",
        abstained=data["status"] != "answered",
        drafts=communication.drafts,
    )
    return data


def load_multiagent_cases():
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(data)
    if json.loads(MANIFEST.read_text(encoding="utf-8")) != manifest():
        raise ValueError("Manifesto multiagente divergente; revise os insumos.")
    return data["cases"]


async def run_multiagent_cases(cases, llm, retriever, temperature=0.1):
    ledger = load_ledger()
    rows = []
    for case in cases:
        # A falta de extrato é parte das armadilhas M16–M18. Nenhum rascunho
        # adversarial ou campo de gabarito é fornecido ao modelo.
        fixture = case.get("validation_fixture")
        transactions = ledger if not fixture or fixture["use_ledger"] else []
        response = await execute_multiagent(case, llm, retriever, temperature, transactions)
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "response": response,
            }
        )
    controlled = []
    for case in cases:
        if "validation_fixture" not in case:
            continue
        fixture = case["validation_fixture"]
        communication = RecordedCommunication(FixtureCommunication(fixture))
        response = await Orchestrator(
            FixtureResearch(), AnalysisAgent(), communication, ValidationAgent()
        ).run(case["question"], ledger if fixture["use_ledger"] else [])
        data = response.model_dump(mode="json")
        data["drafts"] = communication.drafts
        controlled.append({"id": case["id"], "response": data})
    return {"cases": rows, "controlled_validation": controlled}


def numeric_matches(answer, expected):
    """Pontua valores com unidade, tolerância de meio centavo e sinal preservado.

    A presença lexical não prova que o valor foi atribuído à grandeza correta;
    esse vínculo e afirmações proibidas em linguagem natural exigem revisão.
    """
    number = r"[-+]?\s*(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
    unit = expected["unit"]
    pattern = {
        "BRL": rf"(?:R\$\s*({number})(?!\d|[.,]\d)|(?<![\w.,])({number})\s*(?:BRL|reais)\b)",
        "%": rf"(?<![\w.,])({number})\s*%",
        "meses": rf"(?<![\w.,])({number})\s*(?:meses|mês)\b",
    }[unit]
    for match in re.finditer(pattern, answer, re.IGNORECASE):
        raw = next(g for g in match.groups() if g is not None).replace(" ", "")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})+", raw):
            raw = raw.replace(".", "")
        if math.isclose(float(raw), expected["value"], rel_tol=0, abs_tol=0.005):
            return True
    return False


def evaluate_multiagent(cases, raw):
    by_id = {row["id"]: row["response"] for row in raw["cases"]}
    if len(by_id) != len(raw["cases"]) or set(by_id) != {c["id"] for c in cases}:
        raise ValueError("Casos multiagentes ausentes, extras ou duplicados.")
    details = []
    durations = defaultdict(list)
    for case in cases:
        response = by_id[case["id"]]
        answered = response["status"] == "answered"
        numbers = [
            answered and numeric_matches(response["answer"], n) for n in case["expected_numbers"]
        ]
        successful = list(
            dict.fromkeys(s["agent"] for s in response["steps"] if s["status"] == "ok")
        )
        validations = [s for s in response["steps"] if s["agent"] == "validation"]
        blocked = any(s["detail"].get("blockers_count", 0) > 0 for s in validations)
        for agent in ("research", "analysis", "communication", "validation"):
            times = [
                s["duration_ms"]
                for s in response["steps"]
                if s["agent"] == agent and s["status"] != "skipped"
            ]
            if times:
                durations[agent].append(sum(times))
        expected_safe = case["category"] == "armadilha" and case["id"] != "M19"
        # As afirmações proibidas do gabarito são instruções, não padrões
        # literais. Conservamos o conteúdo para a auditoria, sem tratá-lo como prova.
        findings = []
        if answered:
            if numbers and not all(numbers):
                findings.append("Número esperado ausente ou com unidade divergente.")
            reference = " ".join(
                f"R$ {n['value']:.2f}" if n["unit"] == "BRL" else f"{n['value']} {n['unit']}"
                for n in case["expected_numbers"]
            )
            findings += factual_inconsistencies(
                response["answer"],
                {
                    "query": case["question"],
                    "expected_answer": reference,
                },
                [e["content"] for e in response["evidences"]]
                + [f"{c['value']} {c['unit'] or ''}" for c in response["calculations"]],
            )
            if expected_safe:
                findings.append("Resposta à armadilha exige revisão humana.")
        details.append(
            {
                "id": case["id"],
                "category": case["category"],
                "status": response["status"],
                "status_matches_reference": response["status"] == case["expected_status"]
                if "validation_fixture" not in case
                else None,
                "expected_free_behavior": "recusa_segura" if expected_safe else "responder",
                "unexpected_abstention": not answered and not expected_safe,
                "safe_abstention": response["status"] in {"abstained", "rejected"}
                if expected_safe
                else None,
                "agents_match": successful == case["expected_agents"]
                if "validation_fixture" not in case
                else None,
                "numbers_expected": len(numbers),
                "numbers_matched": sum(numbers),
                "numeric_accuracy": fmean(numbers) if numbers else None,
                "concept_recall": concept_recall(
                    response["answer"], [[v] for v in case["required_concepts"]]
                ),
                "validation_executed": bool(validations),
                "validation_blocked": blocked,
                "findings": findings,
                "confirmed": None,
                "forbidden_claims_for_review": case["forbidden_claims"],
            }
        )
    controlled_by_id = {r["id"]: r["response"] for r in raw["controlled_validation"]}
    traps = [c for c in cases if "validation_fixture" in c]
    if len(controlled_by_id) != len(raw["controlled_validation"]) or set(controlled_by_id) != {
        c["id"] for c in traps
    }:
        raise ValueError("Ensaios controlados ausentes, extras ou duplicados.")
    controlled = []
    for case in traps:
        response = controlled_by_id[case["id"]]
        codes = {i["code"] for i in response["validation_issues"] if i["severity"] == "blocker"}
        controlled.append(
            {
                "id": case["id"],
                "expected_code": case["expected_validation_code"],
                "correct_block": response["status"] == "rejected"
                and case["expected_validation_code"] in codes,
            }
        )
    expected = sum(d["numbers_expected"] for d in details)
    matched = sum(d["numbers_matched"] for d in details)
    trap_details = [d for d in details if d["safe_abstention"] is not None]
    categories = {}
    for category in dict.fromkeys(c["category"] for c in cases):
        group = [d for d in details if d["category"] == category]
        total = sum(d["numbers_expected"] for d in group)
        categories[category] = {
            "cases": len(group),
            "answered": sum(d["status"] == "answered" for d in group),
            "numeric_accuracy": sum(d["numbers_matched"] for d in group) / total if total else None,
            "concept_recall": fmean(
                d["concept_recall"] for d in group if d["concept_recall"] is not None
            )
            if any(d["concept_recall"] is not None for d in group)
            else None,
        }
    return {
        "case_count": len(cases),
        "numbers_expected": expected,
        "numbers_matched": matched,
        "numeric_accuracy": matched / expected if expected else None,
        "validation_executed_cases": sum(d["validation_executed"] for d in details),
        "blocked_cases": sum(d["validation_blocked"] for d in details),
        "validation_block_rate": sum(d["validation_blocked"] for d in details) / len(details)
        if details
        else None,
        "correct_blocks_free": None,
        "safe_abstention_rate": fmean(d["safe_abstention"] for d in trap_details)
        if trap_details
        else None,
        "latency_per_agent": {
            agent: {"mean_ms": fmean(times), "executed_cases": len(times)}
            for agent, times in durations.items()
        },
        "categories": categories,
        "case_details": details,
        "controlled_validation": {
            "cases": len(controlled),
            "correct_blocks": sum(d["correct_block"] for d in controlled),
            "details": controlled,
        },
        "limitations": "Métricas lexicais; bloqueios livres e afirmações proibidas "
        "exigem revisão humana. "
        "Uma execução, modelo de 1,5 B e variação observada entre execuções.",
    }


def render_multiagent_markdown(report):
    lines = [
        "",
        "## Cenários novos: agentes",
        "",
        "| Categoria | Casos | Respondidos | Acerto numérico | Cobertura de conceitos |",
        "|---|---:|---:|---:|---:|",
    ]

    def pct(value):
        return "—" if value is None else f"{value:.1%}"

    for category, group in report["categories"].items():
        lines.append(
            f"| {category} | {group['cases']} | {group['answered']} | "
            f"{pct(group['numeric_accuracy'])} | {pct(group['concept_recall'])} |"
        )
    controlled = report["controlled_validation"]
    lines += [
        "",
        f"Recusa segura nas armadilhas livres: {pct(report['safe_abstention_rate'])}.",
        f"Casos com bloqueio na validação: {report['blocked_cases']}/{report['case_count']}. "
        "Correção dos bloqueios livres: revisão humana pendente.",
        f"Ensaio controlado: {controlled['correct_blocks']}/{controlled['cases']} "
        "bloqueios com código esperado. Não mede a frequência de erros do modelo.",
        "",
        report["limitations"],
        "",
    ]
    return "\n".join(lines)


def write_audit_template(report, path: Path):
    """Nunca converte sinalizações em confirmação humana automaticamente."""
    rows = []
    for method, data in report["methods"].items():
        for case in data["case_details"]:
            flagged = bool(case["factual_inconsistencies"])
            if flagged or case["id"] in {"C27", "C29", "C30"}:
                rows.append(
                    {
                        "suite": "semana3",
                        "method": method,
                        "id": case["id"],
                        "flagged": flagged,
                        "confirmed": None,
                        "notes": "",
                    }
                )
    for case in report["multiagent"]["case_details"]:
        if case["findings"] or case["category"] == "armadilha" or case["validation_blocked"]:
            rows.append(
                {
                    "suite": "multiagente",
                    "method": "multiagente",
                    "id": case["id"],
                    "flagged": bool(case["findings"]),
                    "confirmed": None,
                    "block_correct": None,
                    "notes": "",
                }
            )
    if path.exists():
        raise FileExistsError("Auditoria existente; não sobrescrever decisões humanas.")
    path.write_text(
        json.dumps(
            {"status": "pendente", "reviewer": None, "cases": rows}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )


def write_run_registry(args, raw, report):
    """Registra métricas geradas, sem criar números nem revisão humana fictícios."""
    import subprocess

    root = Path(__file__).resolve().parents[2]
    if report["case_count"] != 30 or report["multiagent"]["case_count"] != 20:
        raise ValueError("Registro exige 30 casos históricos e 20 cenários novos.")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True
        ).strip()
    )

    def relative(path):
        return str(path.resolve().relative_to(root))

    run = {
        "schema_version": 2,
        "run_id": args.run_id,
        "date": args.run_id[:10],
        "reference_commit": commit,
        "working_tree_dirty": dirty,
        "issue": "#60",
        "model": args.model or raw["model_name"],
        "provider": raw["provider"],
        "temperature": args.temperature,
        "top_k": 3,
        "max_tokens": 300,
        "repetitions": 1,
        "cases": 30,
        "multiagent_cases": 20,
        "total_case_count": 50,
        "corpus": "20 documentos históricos + 2 fontes suplementares (22 fontes), "
        "iguais para as quatro abordagens",
        "raw_responses": relative(args.output),
        "report": relative(args.report_md),
        "audit": None,
        "audit_pending": relative(args.report_json.parent / "audit_pending.json"),
        "source_of_numbers": "Relatório gerado pelo runner; sinalizações sem confirmação humana.",
        "approaches": {
            key: {
                "label": metrics["label"],
                "f1_tokens": metrics["token_f1"],
                "concept_coverage": metrics["concept_recall"],
                "inconsistency_rate": metrics["factual_inconsistency_rate"],
                "abstention_f1": metrics["abstention_f1"],
                "latency_ms": metrics["latency_mean_ms"],
                "audit": None,
            }
            for key, metrics in report["methods"].items()
        },
        "multiagent": report["multiagent"],
        "notes": "Comparação em 30 casos; 20 cenários novos separados. "
        "Ensaio adversarial controlado não é geração livre. "
        "Uma execução com modelo pequeno; conclusão e auditoria humana pendentes.",
    }
    path = args.output.parent / "run.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(run, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
