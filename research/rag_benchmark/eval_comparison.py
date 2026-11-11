"""Calcula métricas comparativas sobre respostas previamente geradas.

O módulo não chama LLMs nem serviços externos. Recebe o gabarito e o arquivo de
respostas produzido pelo benchmark da issue #24 e grava JSON e Markdown. A
verificação factual é lexical e heurística; não substitui revisão humana.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import fmean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
DEFAULT_CASES = BASE / "questions_comparison.json"
DEFAULT_RESULTS = ROOT / "artifacts/research/comparison_results.json"
DEFAULT_JSON_REPORT = ROOT / "artifacts/research/comparison_report.json"
DEFAULT_MARKDOWN_REPORT = ROOT / "artifacts/research/comparison_report.md"
SOURCE_DIRS = (ROOT / "research/knowledge_base", BASE / "comparison_sources")

METHODS = {
    "llm_pura": {
        "label": "LLM pura",
        "aliases": {"llm_pura", "llm_pure", "pure", "pure_baseline"},
    },
    "rag_ingenuo": {
        "label": "RAG ingênuo",
        "aliases": {"rag_ingenuo", "naive_rag", "naive"},
    },
    "trokim_estruturado": {
        "label": "Trokim estruturado",
        "aliases": {"trokim_estruturado", "trokim_grounded", "grounded"},
    },
}
METHOD_ALIASES = {
    alias: method for method, config in METHODS.items() for alias in config["aliases"]
}

ARTICLES = {"a", "as", "o", "os", "um", "uma", "uns", "umas"}
NEGATIONS = {"nao", "nunca", "jamais", "sem", "nenhum", "nenhuma", "nem"}
STOPWORDS = (
    ARTICLES
    | NEGATIONS
    | {
        "ao",
        "aos",
        "com",
        "como",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "entre",
        "mas",
        "nos",
        "ou",
        "para",
        "pela",
        "pelas",
        "pelo",
        "pelos",
        "por",
        "que",
        "se",
        "sob",
        "sobre",
        "um",
        "uma",
        "seu",
        "sua",
        "seus",
        "suas",
        "ser",
        "ter",
        "estar",
        "é",
        "são",
        "foi",
        "foram",
    }
)
NUMBER_PATTERN = re.compile(
    r"(?<![\w])(?P<currency>R\$|US\$|USD)?\s*"
    r"(?P<number>\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?|\d+(?:\.\d+)?)"
    r"\s*(?P<percent>%)?",
    re.IGNORECASE,
)
SENTENCE_PATTERN = re.compile(r"(?<=[.!?;])\s+|\n+")


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def normalize_tokens(text: str) -> list[str]:
    """Normaliza pt-BR, remove pontuação e artigos como no SQuAD F1."""
    return [token for token in re.findall(r"[a-z0-9]+", _ascii(text)) if token not in ARTICLES]


def token_f1(prediction: str, reference: str) -> float:
    """F1 de unigramas com contagem multiconjunto e normalização SQuAD."""
    predicted = normalize_tokens(prediction)
    expected = normalize_tokens(reference)
    if not predicted and not expected:
        return 1.0
    if not predicted or not expected:
        return 0.0

    overlap = sum((Counter(predicted) & Counter(expected)).values())
    precision = overlap / len(predicted)
    recall = overlap / len(expected)
    return 2 * precision * recall / (precision + recall) if overlap else 0.0


def _contains_phrase(text_tokens: list[str], phrase_tokens: list[str]) -> bool:
    if not phrase_tokens or len(phrase_tokens) > len(text_tokens):
        return False
    width = len(phrase_tokens)
    return any(
        text_tokens[index : index + width] == phrase_tokens
        for index in range(len(text_tokens) - width + 1)
    )


def concept_recall(answer: str, concepts: list[list[str]]) -> float | None:
    """Recall de conceitos; cada grupo conta uma vez e aceita termos alternativos."""
    if not concepts:
        return None
    answer_tokens = normalize_tokens(answer)
    covered = sum(
        any(_contains_phrase(answer_tokens, normalize_tokens(term)) for term in alternatives)
        for alternatives in concepts
    )
    return covered / len(concepts)


def _canonical_number(raw: str) -> str:
    value = raw.replace(" ", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value):
        value = value.replace(".", "")
    try:
        return format(Decimal(value).normalize(), "f")
    except InvalidOperation:
        return value


def _numeric_facts(text: str) -> set[tuple[str, str]]:
    facts = set()
    for match in NUMBER_PATTERN.finditer(text):
        unit = (
            "percent"
            if match.group("percent")
            else "currency"
            if match.group("currency")
            else "unknown"
        )
        facts.add((_canonical_number(match.group("number")), unit))
    return facts


def _number_is_supported(fact: tuple[str, str], supported: set[tuple[str, str]]) -> bool:
    value, unit = fact
    return any(
        known_value == value and (known_unit == unit or "unknown" in {known_unit, unit})
        for known_value, known_unit in supported
    )


def _format_number_fact(value: str, unit: str) -> str:
    suffix = "%" if unit == "percent" else " (moeda)" if unit == "currency" else ""
    return f"número sem suporte: {value}{suffix}"


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in SENTENCE_PATTERN.split(text) if sentence.strip()]


def _content_tokens(text: str) -> set[str]:
    return set(normalize_tokens(text)) - STOPWORDS


def _has_negation(text: str) -> bool:
    return bool(set(normalize_tokens(text)) & NEGATIONS)


def _contradictions(answer: str, trusted_texts: list[str]) -> list[str]:
    findings = set()
    answer_sentences = _sentences(answer)
    source_sentences = [sentence for text in trusted_texts for sentence in _sentences(text)]
    for answer_sentence in answer_sentences:
        answer_tokens = _content_tokens(answer_sentence)
        if len(answer_tokens) < 2:
            continue
        for source_sentence in source_sentences:
            source_tokens = _content_tokens(source_sentence)
            shared = answer_tokens & source_tokens
            union = answer_tokens | source_tokens
            similarity = len(shared) / len(union) if union else 0.0
            if (
                len(shared) >= 2
                and similarity >= 0.5
                and _has_negation(answer_sentence) != _has_negation(source_sentence)
            ):
                findings.add(f"possível contradição por negação: {answer_sentence[:180]}")
                break
    return sorted(findings)


def factual_inconsistencies(
    answer: str,
    case: dict[str, Any],
    relevant_sources: list[str],
) -> list[str]:
    """Aplica regras locais: números sem suporte, frases proibidas literais e negação.

    Os números da pergunta são admitidos como dados fornecidos pelo usuário; o
    valor calculado precisa aparecer na resposta de referência ou nas fontes.
    """
    if not answer.strip():
        return []

    reference = str(case.get("expected_answer", ""))
    query = str(case.get("query", ""))
    factual_sources = [reference, *relevant_sources]
    supported_numbers = _numeric_facts("\n".join([query, *factual_sources]))
    findings = {
        _format_number_fact(value, unit)
        for value, unit in _numeric_facts(answer)
        if not _number_is_supported((value, unit), supported_numbers)
    }
    findings.update(_contradictions(answer, factual_sources))

    normalized_answer = normalize_tokens(answer)
    for claim in case.get("forbidden_claims", []):
        if _contains_phrase(normalized_answer, normalize_tokens(claim)):
            findings.add(f"afirmação proibida literal: {claim}")
    return sorted(findings)


def expected_abstention(case: dict[str, Any]) -> bool:
    behavior = case.get("expected_behavior")
    if behavior is not None:
        if behavior not in {"responder", "corrigir_premissa", "abster"}:
            raise ValueError(f"Comportamento esperado inválido: {behavior}")
        return behavior == "abster"
    if "expected_abstention" in case:
        if not isinstance(case["expected_abstention"], bool):
            raise ValueError("expected_abstention deve ser booleano.")
        return case["expected_abstention"]
    return not bool(case.get("relevant"))


def predicted_abstention(response: dict[str, Any]) -> bool:
    signals = []
    if "abstained" in response:
        if not isinstance(response["abstained"], bool):
            raise ValueError("abstained deve ser booleano.")
        signals.append(response["abstained"])
    if "answered" in response:
        if not isinstance(response["answered"], bool):
            raise ValueError("answered deve ser booleano.")
        signals.append(not response["answered"])
    if "status" in response:
        valid_statuses = {"grounded", "abstained", "pure_baseline", "naive_rag"}
        if response["status"] not in valid_statuses:
            raise ValueError(f"Status de resposta inválido: {response['status']}")
        signals.append(response["status"] == "abstained")
    if not signals:
        raise ValueError("Resposta precisa de status, answered ou abstained.")
    if any(signal != signals[0] for signal in signals[1:]):
        raise ValueError("status, answered e abstained são inconsistentes entre si.")
    return signals[0]


def abstention_metrics(expected: list[bool], predicted: list[bool]) -> dict[str, int | float]:
    if len(expected) != len(predicted):
        raise ValueError("As listas de abstenção devem ter o mesmo tamanho.")
    tp = sum(actual and guess for actual, guess in zip(expected, predicted, strict=True))
    fp = sum(not actual and guess for actual, guess in zip(expected, predicted, strict=True))
    fn = sum(actual and not guess for actual, guess in zip(expected, predicted, strict=True))
    tn = sum(not actual and not guess for actual, guess in zip(expected, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def load_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for directory in SOURCE_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("*.txt"):
            if path.name in sources:
                raise ValueError(f"Fonte duplicada nos catálogos: {path.name}")
            sources[path.name] = path.read_text(encoding="utf-8")
    return sources


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("O gabarito precisa conter uma lista não vazia de casos.")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Cada caso do gabarito precisa ser um objeto JSON.")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError("IDs dos casos devem ser únicos e não vazios.")
        seen.add(case_id)
        if not all(
            isinstance(case.get(key), str) and case[key].strip()
            for key in ("query", "expected_answer")
        ):
            raise ValueError(f"{case_id}: query e expected_answer são obrigatórios.")
        concepts = case.get("concepts")
        if not isinstance(concepts, list) or any(
            not isinstance(group, list)
            or not group
            or any(not isinstance(term, str) or not term.strip() for term in group)
            for group in concepts
        ):
            raise ValueError(f"{case_id}: concepts deve conter grupos de termos não vazios.")
        relevant = case.get("relevant", [])
        if not isinstance(relevant, list) or any(not isinstance(item, str) for item in relevant):
            raise ValueError(f"{case_id}: relevant deve ser uma lista de IDs de fonte.")
        forbidden_claims = case.get("forbidden_claims", [])
        if not isinstance(forbidden_claims, list) or any(
            not isinstance(item, str) or not item.strip() for item in forbidden_claims
        ):
            raise ValueError(f"{case_id}: forbidden_claims deve ser uma lista de textos.")
        expected_abstention(case)
    return cases


def _method_name(name: str) -> str | None:
    return METHOD_ALIASES.get(name.strip().lower())


def normalize_results(data: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    rows = data.get("cases")
    if not isinstance(rows, list):
        raise ValueError("Resultados devem conter a lista 'cases'.")
    normalized: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Cada resultado precisa de um ID de caso.")
        case_id = row["id"]
        if case_id in normalized:
            raise ValueError(f"Resultado duplicado para o caso {case_id}.")
        responses = row.get("responses", row.get("systems"))
        if responses is None:
            responses = {key: value for key, value in row.items() if _method_name(key)}
        if not isinstance(responses, dict):
            raise ValueError(f"{case_id}: responses deve ser um objeto por abordagem.")
        by_method = {}
        for raw_name, response in responses.items():
            method = _method_name(raw_name)
            if method is None:
                continue
            if method in by_method:
                raise ValueError(f"{case_id}: abordagem duplicada ({method}).")
            if not isinstance(response, dict) or not isinstance(response.get("answer"), str):
                raise ValueError(f"{case_id}/{method}: answer deve ser texto.")
            predicted_abstention(response)
            by_method[method] = response
        normalized[case_id] = by_method
    return normalized


def _mean(values: list[float]) -> float | None:
    return fmean(values) if values else None


def evaluate_comparison(
    cases: list[dict[str, Any]],
    results: dict[str, Any],
    sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compara as três abordagens sem executar geração ou acesso à rede."""
    source_map = sources if sources is not None else load_sources()
    responses_by_case = normalize_results(results)
    case_ids = [case["id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("O gabarito contém IDs duplicados.")
    if set(responses_by_case) != set(case_ids):
        missing = sorted(set(case_ids) - set(responses_by_case))
        extra = sorted(set(responses_by_case) - set(case_ids))
        raise ValueError(f"IDs de resultado divergentes; ausentes={missing}, extras={extra}.")

    methods_report = {}
    for method, config in METHODS.items():
        token_scores: list[float] = []
        concept_scores: list[float] = []
        expected_abstentions: list[bool] = []
        actual_abstentions: list[bool] = []
        inconsistency_count = 0
        answered_count = 0
        details = []

        for case in cases:
            case_id = case["id"]
            response = responses_by_case[case_id].get(method)
            if response is None:
                raise ValueError(f"{case_id}: resposta ausente para {method}.")
            answer = response["answer"]
            abstained = predicted_abstention(response)
            expected_abstain = expected_abstention(case)
            expected_abstentions.append(expected_abstain)
            actual_abstentions.append(abstained)

            f1 = None if expected_abstain else token_f1(answer, case["expected_answer"])
            if f1 is not None:
                token_scores.append(f1)
            recall = concept_recall(answer, case["concepts"])
            if recall is not None:
                concept_scores.append(recall)

            relevant = case.get("relevant", [])
            unknown_sources = sorted(set(relevant) - source_map.keys())
            if unknown_sources:
                raise ValueError(
                    f"{case_id}: fontes relevantes não encontradas: {unknown_sources}."
                )
            findings = (
                factual_inconsistencies(answer, case, [source_map[name] for name in relevant])
                if not abstained
                else []
            )
            answered_count += not abstained
            inconsistency_count += bool(findings)
            details.append(
                {
                    "id": case_id,
                    "answer": answer,
                    "expected_abstention": expected_abstain,
                    "predicted_abstention": abstained,
                    "token_f1": f1,
                    "concept_recall": recall,
                    "factual_inconsistencies": findings,
                }
            )

        abstention = abstention_metrics(expected_abstentions, actual_abstentions)
        methods_report[method] = {
            "label": config["label"],
            "cases": len(cases),
            "answered": answered_count,
            "token_f1": _mean(token_scores),
            "concept_recall": _mean(concept_scores),
            "factual_inconsistency_rate": inconsistency_count / answered_count
            if answered_count
            else None,
            "inconsistent_answers": inconsistency_count,
            "abstention_f1": abstention["f1"],
            "abstention": abstention,
            "case_details": details,
        }

    return {
        "schema_version": 1,
        "methodology": {
            "token_f1": (
                "Média SQuAD F1 nos casos que esperam resposta: unigramas em minúsculas, "
                "sem acentos, pontuação ou artigos e com contagem multiconjunto."
            ),
            "concept_recall": (
                "Cada grupo de conceitos vale uma unidade; qualquer alternativa textual "
                "contígua cobre o grupo."
            ),
            "factual_inconsistency_rate": (
                "Proporção de respostas não abstidas com número sem suporte, frase proibida "
                "literal ou contradição heurística por negação."
            ),
            "limitations": (
                "As regras factuais são lexicais, não comprovam entailment semântico e exigem "
                "revisão humana dos casos sinalizados."
            ),
        },
        "case_count": len(cases),
        "methods": methods_report,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Relatório comparativo de respostas",
        "",
        f"Casos avaliados: **{report['case_count']}**.",
        "",
        "| Abordagem | F1 de tokens | Concept recall | Inconsistência factual | Abstention F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        metrics = report["methods"][method]

        def percent(value: float | None) -> str:
            return "—" if value is None else f"{value:.1%}"

        lines.append(
            "| {label} | {token} | {concept} | {factual} | {abstention} |".format(
                label=metrics["label"],
                token=percent(metrics["token_f1"]),
                concept=percent(metrics["concept_recall"]),
                factual=percent(metrics["factual_inconsistency_rate"]),
                abstention=percent(metrics["abstention_f1"]),
            )
        )
    lines.extend(
        [
            "",
            (
                "A taxa factual é uma heurística lexical, não uma prova semântica. "
                "Respostas sinalizadas exigem revisão humana."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Gabarito da issue #20.")
    parser.add_argument(
        "--results", type=Path, default=DEFAULT_RESULTS, help="Respostas geradas pela issue #24."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_REPORT)
    args = parser.parse_args(argv)

    try:
        cases = load_cases(args.cases)
        results = json.loads(args.results.read_text(encoding="utf-8"))
        if not isinstance(results, dict):
            raise ValueError("O arquivo de resultados precisa ser um objeto JSON.")
        report = evaluate_comparison(cases, results)
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"Erro na avaliação comparativa: {exc}", file=sys.stderr)
        return 2

    print(f"Relatório JSON: {args.json_output}")
    print(f"Relatório Markdown: {args.markdown_output}")
    for metrics in report["methods"].values():
        score = metrics["factual_inconsistency_rate"]
        print(f"{metrics['label']}: taxa de inconsistência {score if score is not None else 'N/A'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
