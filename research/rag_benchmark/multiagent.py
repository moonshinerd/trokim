"""Valida os insumos multiagentes e regenera números e hashes após revisão (#56)."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from app.domain.models import Transaction  # noqa: E402
from app.services.calculation_service import CalculationService  # noqa: E402

LEDGER = ROOT / "research/synthetic_data/ledger_multiagente.json"
GENERATOR = ROOT / "research/synthetic_data/generate_ledger_multiagente.py"
QUESTIONS = Path(__file__).with_name("questions_multiagent.json")
SCHEMA = Path(__file__).with_name("questions_multiagent.schema.json")
MANIFEST = Path(__file__).with_name("multiagent_manifest.json")
HASHED = [LEDGER, GENERATOR, QUESTIONS, SCHEMA, Path(__file__).resolve()]


def manifest() -> dict:
    return {
        "schema_version": 1,
        "hash_algorithm": "sha256-bytes",
        "files": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(HASHED)
        },
    }


def load_ledger() -> list[Transaction]:
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    return [Transaction(**tx) for tx in data["transactions"]]


def resolve(key: str, params: dict, ledger: list[Transaction]) -> float:
    """Recalcula cada número exclusivamente pela interface pública de cálculo."""
    summary = CalculationService.calculate_summary(ledger)
    if key in {"total_income", "total_expenses", "net_balance", "savings_rate"}:
        return getattr(summary, key)
    if key == "category_expense":
        return summary.expenses_by_category[params["category"]]
    if key == "category_share":
        return CalculationService.category_shares(summary)[params["category"]]
    if key == "months_to_goal":
        return CalculationService.months_to_goal(params["goal"], params["monthly_savings"])
    raise KeyError(key)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-manifest", action="store_true", help="Regenera os hashes revisados"
    )
    parser.add_argument(
        "--write-expected-numbers", action="store_true", help="Regenera os números pelo serviço"
    )
    args = parser.parse_args()
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)
    ledger = load_ledger()
    for case in data["cases"]:
        for number in case["expected_numbers"]:
            calculated = resolve(number["key"], number.get("params", {}), ledger)
            if args.write_expected_numbers:
                number["value"] = calculated
            elif abs(number["value"] - calculated) > 0.005:
                raise ValueError(f"Número divergente em {case['id']}: {number['key']}")
    if args.write_expected_numbers:
        QUESTIONS.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    current = manifest()
    if args.write_manifest:
        MANIFEST.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    elif json.loads(MANIFEST.read_text(encoding="utf-8")) != current:
        raise ValueError("Manifesto desatualizado: revise o conteúdo antes de regenerar os hashes.")
    print("Material multiagente válido: 20 casos, números e hashes conferidos.")


if __name__ == "__main__":
    main()
