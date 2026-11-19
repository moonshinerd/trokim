"""Benchmark dos 20 cenários multiagente da Semana 4 (#60), com o extrato sintético.

Dois ensaios, como pede o gabarito (`docs/pesquisa/gabarito-multiagente.md`):

1. **Livre:** as 20 perguntas passam pelo orquestrador real (Research no corpus unificado de
   22 fontes, Analysis, Communication com o modelo e Validation), com o extrato sintético só
   quando o gabarito pede (``use_ledger``: M16 a M18 vão sem extrato). Mede status, agentes com
   passo `ok`, acerto numérico (valor com unidade e sinal), cobertura de conceitos, bloqueios do
   Validation, falhas do modelo e latência por agente.
2. **Rascunho injetado:** nas 5 armadilhas, Research e Communication são controlados e o
   rascunho inválido do gabarito é injetado; Analysis, Orchestrator e Validation são reais.
   Mede se o Validation bloqueia com o código esperado. Não usa modelo.

As peças comuns (gravação das respostas originais e dos rascunhos, corpus, registro e
formulário de auditoria) estão em ``multiagent_benchmark``.

Uso, pela raiz: ``make multiagent-run RUN=<id> MODEL=<modelo>``; para refazer só o relatório a
partir das respostas gravadas: ``--output-dir <pasta> --reavaliar``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(BASE))

from eval_comparison import concept_recall  # noqa: E402
from multiagent import load_ledger  # noqa: E402
from multiagent_benchmark import (  # noqa: E402
    RESULTS,
    ComparisonRAG,
    add_scenarios_to_registry,
    check_new_run,
    execute_injected,
    execute_multiagent,
    load_multiagent_cases,
    model_failed,
    numeric_matches,
    scenario_audit_rows,
    write_audit_template,
)

AGENTS = ["research", "analysis", "communication", "validation"]
# Armadilha só na versão injetada: a pergunta livre do M19 pede um saldo legítimo.
FREE_TRAPS_ANSWERABLE = {"M19"}


def successful_agents(steps: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(step["agent"] for step in steps if step["status"] == "ok"))


def uses_ledger(case: dict[str, Any]) -> bool:
    fixture = case.get("validation_fixture")
    return not fixture or fixture["use_ledger"]


async def run_free(
    cases: list[dict[str, Any]], llm: Any, temperature: float, retriever: Any = None
) -> list[dict[str, Any]]:
    if retriever is None:
        from run_comparison import UnifiedCorpusRetriever

        retriever = UnifiedCorpusRetriever()
    source = ComparisonRAG(retriever)
    ledger = load_ledger()
    rows = []
    for idx, case in enumerate(cases, 1):
        print(f"[livre {idx:02d}/{len(cases)}] {case['id']} ({case['category']})")
        row = await execute_multiagent(
            case["question"],
            llm,
            source,
            temperature=temperature,
            transactions=ledger if uses_ledger(case) else [],
        )
        rows.append({"id": case["id"], **row})
    return rows


async def run_injected(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ledger = load_ledger()
    return [{"id": case["id"], **await execute_injected(case, ledger)} for case in cases]


def evaluate(
    cases: list[dict[str, Any]], free: list[dict[str, Any]], injected: list[dict[str, Any]]
) -> dict[str, Any]:
    by_id = {row["id"]: row for row in free}
    details = []
    for case in cases:
        row = by_id[case["id"]]
        trap = case["category"] == "armadilha" and case["id"] not in FREE_TRAPS_ANSWERABLE
        answered = row["status"] == "answered"
        numbers = [answered and numeric_matches(row["answer"], n) for n in case["expected_numbers"]]
        failed = row.get("model_failed", model_failed(row["steps"]))
        details.append(
            {
                "id": case["id"],
                "category": case["category"],
                "status": row["status"],
                # Armadilha livre: abster ou reter é o comportamento seguro; responder exige
                # revisão humana (a pergunta não traz o rascunho inválido do ensaio injetado).
                # Falha do modelo nunca conta como comportamento esperado.
                "status_ok": not failed and ((not answered) if trap else answered),
                "agents_ok": None
                if case["category"] == "armadilha"
                else successful_agents(row["steps"]) == case["expected_agents"],
                "numbers_expected": len(numbers),
                "numbers_reproduced": sum(numbers),
                "concept_recall": concept_recall(
                    row["answer"], [[c] for c in case["required_concepts"]]
                )
                if answered and case["required_concepts"]
                else None,
                "blocked": any(i["severity"] == "blocker" for i in row["validation_issues"]),
                "revisions": max(0, sum(s["agent"] == "communication" for s in row["steps"]) - 1),
                "codes": sorted({i["code"] for i in row["validation_issues"]}),
                "needs_review": trap and answered,
                # Communication sem resposta do modelo (tempo limite, indisponível): não é
                # bloqueio do Validation e é contado à parte.
                "model_failed": failed,
                "latency_ms": row["latency_ms"],
            }
        )

    by_category: dict[str, dict[str, Any]] = {}
    for category in ("evidencia", "calculo", "evidencia_calculo", "armadilha"):
        rows = [d for d in details if d["category"] == category]
        expected = sum(d["numbers_expected"] for d in rows)
        concepts = [d["concept_recall"] for d in rows if d["concept_recall"] is not None]
        by_category[category] = {
            "cases": len(rows),
            "status_ok": sum(d["status_ok"] for d in rows),
            "answered": sum(d["status"] == "answered" for d in rows),
            "abstained": sum(d["status"] == "abstained" for d in rows),
            "rejected": sum(d["status"] == "rejected" for d in rows),
            "numbers_expected": expected,
            "numbers_reproduced": sum(d["numbers_reproduced"] for d in rows),
            "concept_recall": fmean(concepts) if concepts else None,
            "blocked": sum(d["blocked"] for d in rows),
            "model_failed": sum(d["model_failed"] for d in rows),
        }

    latency_by_agent = {}
    for agent in AGENTS:
        durations = [
            s["duration_ms"]
            for row in free
            for s in row["steps"]
            if s["agent"] == agent and s["status"] != "skipped"
        ]
        latency_by_agent[agent] = round(fmean(durations), 1) if durations else None

    expected_numbers = sum(d["numbers_expected"] for d in details)
    regular = [d for d in details if d["category"] != "armadilha"]
    injected_by_id = {row["id"]: row for row in injected}
    injected_details = []
    for case in cases:
        if case["category"] != "armadilha":
            continue
        row = injected_by_id[case["id"]]
        codes = {i["code"] for i in row["validation_issues"]}
        injected_details.append(
            {
                "id": case["id"],
                "status": row["status"],
                "expected_code": case["expected_validation_code"],
                "codes": sorted(codes),
                "blocked_with_expected_code": row["status"] == "rejected"
                and case["expected_validation_code"] in codes,
                "draft_retained": row["draft_retained"],
            }
        )

    blocked = [d for d in details if d["blocked"]]
    return {
        "schema_version": 1,
        "case_count": len(details),
        "free": {
            "status_ok": sum(d["status_ok"] for d in details),
            "regular_answered": sum(d["status"] == "answered" for d in regular),
            "regular_cases": len(regular),
            "agents_ok": sum(bool(d["agents_ok"]) for d in regular),
            "numbers_expected": expected_numbers,
            "numbers_reproduced": sum(d["numbers_reproduced"] for d in details),
            "numeric_accuracy": sum(d["numbers_reproduced"] for d in details) / expected_numbers
            if expected_numbers
            else None,
            "validation_block_rate": len(blocked) / len(details),
            "blocked_cases": [d["id"] for d in blocked],
            "traps_safe": sum(
                d["status_ok"]
                for d in details
                if d["category"] == "armadilha" and d["id"] not in FREE_TRAPS_ANSWERABLE
            ),
            "traps_free_cases": sum(
                d["category"] == "armadilha" and d["id"] not in FREE_TRAPS_ANSWERABLE
                for d in details
            ),
            "model_failures": [d["id"] for d in details if d["model_failed"]],
            "traps_needing_review": [d["id"] for d in details if d["needs_review"]],
            "latency_mean_ms": round(fmean(d["latency_ms"] for d in details), 1),
            "latency_by_agent_ms": latency_by_agent,
            "by_category": by_category,
            "case_details": details,
        },
        "injected": {
            "cases": len(injected_details),
            "blocked_with_expected_code": sum(
                d["blocked_with_expected_code"] for d in injected_details
            ),
            "drafts_retained": sum(d["draft_retained"] for d in injected_details),
            "case_details": injected_details,
        },
        "methodology": {
            "status_ok": (
                "Casos regulares e M19 livre: status answered. Armadilhas M16-M18 e M20 no "
                "ensaio livre: abstained ou rejected (responder fica para revisão humana). "
                "Falha do modelo nunca conta."
            ),
            "numeric_accuracy": (
                "Número do gabarito na resposta dada, com unidade (R$/BRL, %, meses) e sinal; "
                "BRL com tolerância de 0,005, percentual com uma casa decimal e meses exatos. "
                "Recusa perde os acertos."
            ),
            "concept_recall": "Mesmo critério lexical da Semana 3, só nas respostas dadas.",
            "validation_block_rate": "Casos com ao menos um bloqueio do Validation.",
            "limitations": (
                "Uma execução, gabarito público e não cego; heurísticas lexicais exigem "
                "revisão humana dos casos sinalizados."
            ),
        },
    }


def render_markdown(report: dict[str, Any], model: str) -> str:
    free, injected = report["free"], report["injected"]

    def pct(value: float | None) -> str:
        return "—" if value is None else f"{value:.1%}".replace(".", ",")

    names = {
        "evidencia": "Evidência",
        "calculo": "Cálculo",
        "evidencia_calculo": "Evidência + cálculo",
        "armadilha": "Armadilha",
    }
    lines = [
        "# Benchmark multiagente: 20 cenários",
        "",
        f"Modelo: `{model}`. Casos: **{report['case_count']}**.",
        "",
        "## Ensaio livre",
        "",
        "| Categoria | Casos | Comportamento esperado | Respondidas | Abstenções | Rejeições "
        "| Números reproduzidos | Cobertura de conceitos |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in free["by_category"].items():
        numbers = (
            f"{row['numbers_reproduced']}/{row['numbers_expected']}"
            if row["numbers_expected"]
            else "—"
        )
        lines.append(
            f"| {names[key]} | {row['cases']} | {row['status_ok']} | {row['answered']} "
            f"| {row['abstained']} | {row['rejected']} | {numbers} "
            f"| {pct(row['concept_recall'])} |"
        )
    agents = ", ".join(
        f"{agent} {value:.0f} ms" for agent, value in free["latency_by_agent_ms"].items() if value
    )
    lines += [
        "",
        f"- Acerto numérico: **{free['numbers_reproduced']}/{free['numbers_expected']}** "
        f"({pct(free['numeric_accuracy'])}).",
        f"- Agentes com passo `ok` iguais ao gabarito: {free['agents_ok']}/"
        f"{free['regular_cases']} casos regulares.",
        f"- Taxa de bloqueio do Validation: {pct(free['validation_block_rate'])} "
        f"({', '.join(free['blocked_cases']) or 'nenhum caso'}).",
        f"- Armadilhas com comportamento seguro: {free['traps_safe']}/{free['traps_free_cases']} "
        "(M19 livre pede um saldo legítimo e fica fora); para revisão humana: "
        f"{', '.join(free['traps_needing_review']) or 'nenhuma'}.",
        f"- Falhas do modelo (Communication sem resposta): "
        f"{', '.join(free['model_failures']) or 'nenhuma'}.",
        f"- Latência média: {free['latency_mean_ms']:.0f} ms; por agente: {agents}.",
        "",
        "## Ensaio com rascunho injetado (armadilhas)",
        "",
        "| Caso | Status | Código esperado | Códigos | Bloqueou com o código | Rascunho retido |",
        "|---|---|---|---|:---:|:---:|",
    ]
    for row in injected["case_details"]:
        blocked = "sim" if row["blocked_with_expected_code"] else "não"
        retained = "sim" if row["draft_retained"] else "não"
        lines.append(
            f"| {row['id']} | {row['status']} | `{row['expected_code']}` "
            f"| {', '.join(row['codes'])} | {blocked} | {retained} |"
        )
    lines += ["", report["methodology"]["limitations"], ""]
    return "\n".join(lines)


def write_report(out: Path, report: dict[str, Any], model: str) -> str:
    (out / "multiagent_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = render_markdown(report, model)
    (out / "multiagent_report.md").write_text(markdown, encoding="utf-8")
    return markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="Modelo no formato do LiteLLM.")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--run-id", help="Grava em results/multiagent/<run-id>/ (pasta nova).")
    parser.add_argument("--output-dir", type=Path, help="Pasta de saída, sem --run-id.")
    parser.add_argument(
        "--reavaliar",
        action="store_true",
        help="Só refaz o relatório a partir do multiagent_results.json já gravado (sem modelo).",
    )
    args = parser.parse_args(argv)
    out = RESULTS / "multiagent" / args.run_id if args.run_id else args.output_dir
    if out is None:
        parser.error("informe --run-id ou --output-dir")
    cases = load_multiagent_cases()

    if args.reavaliar:
        raw = json.loads((out / "multiagent_results.json").read_text(encoding="utf-8"))
        report = evaluate(cases, raw["free"], raw["injected"])
        print(write_report(out, report, raw["model"]))
        # Mesmas respostas, avaliador novo: o resumo do run.json acompanha o relatório.
        add_scenarios_to_registry(out.name, report, replace=True)
        return 0
    if not args.model:
        parser.error("--model é obrigatório, exceto com --reavaliar")
    if args.run_id:
        check_new_run(args.run_id, out)

    from app.clients.litellm_provider import LiteLLMProvider

    llm = LiteLLMProvider(model=args.model, timeout=args.timeout)
    free = asyncio.run(run_free(cases, llm, args.temperature))
    injected = asyncio.run(run_injected([c for c in cases if c["category"] == "armadilha"]))
    report = evaluate(cases, free, injected)

    out.mkdir(parents=True, exist_ok=True)
    raw = {
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "temperature": args.temperature,
        "free": free,
        "injected": injected,
    }
    (out / "multiagent_results.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(write_report(out, report, args.model))
    if args.run_id:
        write_audit_template(out / "audit_pending.json", scenario_audit_rows(report))
        if add_scenarios_to_registry(args.run_id, report):
            print(f"Resumo dos cenários acrescentado ao run.json de {args.run_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
