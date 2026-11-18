"""Valida o gabarito multiagente: schema, manifesto e números calculados do ledger sintético."""

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError, validate

from app.domain.models import FinancialSummary, Transaction
from app.services.calculation_service import CalculationService

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "research/synthetic_data/ledger_multiagente.json"
GENERATOR = ROOT / "research/synthetic_data/generate_ledger_multiagente.py"
QUESTIONS = ROOT / "research/rag_benchmark/questions_multiagent.json"
SCHEMA = ROOT / "research/rag_benchmark/questions_multiagent.schema.json"
MANIFEST = ROOT / "research/rag_benchmark/multiagent_manifest.json"
MESES_DO_LEDGER = 3
HASHED = [LEDGER, GENERATOR, QUESTIONS, SCHEMA]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest() -> dict:
    return {
        "schema_version": 1,
        "hash_algorithm": "sha256-bytes",
        "files": {str(p.relative_to(ROOT)): sha256(p) for p in sorted(HASHED)},
    }


def load_ledger() -> list[Transaction]:
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    return [Transaction(**tx) for tx in data["transactions"]]


def resolve(key: str, params: dict, ledger: list[Transaction]) -> float:
    """Calcula o valor esperado de uma chave a partir do ledger, sempre via CalculationService."""
    summary: FinancialSummary = CalculationService.calculate_summary(ledger)
    avg_net = summary.net_balance / MESES_DO_LEDGER
    avg_expenses = summary.total_expenses / MESES_DO_LEDGER
    if key == "total_income":
        return summary.total_income
    if key == "total_expenses":
        return summary.total_expenses
    if key == "net_balance":
        return summary.net_balance
    if key == "savings_rate":
        return summary.savings_rate
    if key == "category_expense":
        return summary.expenses_by_category[params["category"]]
    if key == "category_share":
        return CalculationService.category_shares(summary)[params["category"]]
    if key == "months_to_goal":
        monthly = params["monthly_savings"]
        monthly = avg_net if monthly == "avg_monthly_net_balance" else monthly
        return CalculationService.months_to_goal(params["goal"], monthly)
    if key == "reserve_coverage_months":
        return round(summary.net_balance / avg_expenses, 2)
    if key == "duplicates_ignored":
        return sum(1 for tx in ledger if tx.is_duplicate)
    raise KeyError(key)


def test_manifesto_confere_hashes():
    assert json.loads(MANIFEST.read_text(encoding="utf-8")) == manifest()


def test_gabarito_valida_pelo_schema_e_tem_composicao_esperada():
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validate(cases, schema)
    counts: dict[str, int] = {}
    for case in cases["cases"]:
        counts[case["category"]] = counts.get(case["category"], 0) + 1
    assert counts == {"evidencia": 5, "calculo": 5, "evidencia_calculo": 5, "armadilha": 5}
    assert len({c["id"] for c in cases["cases"]}) == 20
    assert len({c["question"] for c in cases["cases"]}) == 20


def test_ledger_e_reproduzivel_pelo_gerador():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_ledger", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build() == json.loads(LEDGER.read_text(encoding="utf-8"))


def test_ledger_tem_duplicatas_e_tres_meses():
    ledger = load_ledger()
    assert any(tx.is_duplicate for tx in ledger)
    assert len({(tx.date.year, tx.date.month) for tx in ledger}) == MESES_DO_LEDGER


def _numeros():
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    return [(c["id"], n) for c in data["cases"] for n in c["expected_numbers"]]


@pytest.mark.parametrize(
    ("case_id", "number"), _numeros(), ids=lambda v: v if isinstance(v, str) else v["key"]
)
def test_numeros_do_gabarito_batem_com_calculation_service(case_id, number):
    esperado = resolve(number["key"], number.get("params", {}), load_ledger())
    assert math.isclose(number["value"], esperado, abs_tol=0.005), case_id


def test_status_agentes_e_codigos_sao_coerentes():
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        if case["category"] == "armadilha":
            assert case["expected_status"] in {"abstained", "rejected"}
            assert case["expected_validation_code"]
        else:
            assert case["expected_status"] == "answered"
        has_numbers = bool(case["expected_numbers"])
        assert has_numbers == (case["category"] in {"calculo", "evidencia_calculo"})
        assert ("analysis" in case["expected_agents"]) == has_numbers or case[
            "category"
        ] == "armadilha"


def test_schema_rejeita_gabarito_invalido():
    cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for mutate in (
        lambda d: d["cases"].pop(),
        lambda d: d["cases"][0].update(expected_status="talvez"),
        lambda d: d["cases"][0].update(extra=1),
        lambda d: d["cases"][0].update(expected_validation_code="OUT_OF_SCOPE_ADVICE"),
        lambda d: d["cases"][-1].update(expected_validation_code=None),
    ):
        broken = copy.deepcopy(cases)
        mutate(broken)
        with pytest.raises(ValidationError):
            validate(broken, schema)
