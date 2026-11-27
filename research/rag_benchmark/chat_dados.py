import argparse
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

Account = __import__("app.domain.models", fromlist=["Account"]).Account
Statement = __import__("app.domain.models", fromlist=["Statement"]).Statement
Transaction = __import__("app.domain.models", fromlist=["Transaction"]).Transaction
CalculationService = __import__(
    "app.services.calculation_service", fromlist=["CalculationService"]
).CalculationService
Library = __import__("app.services.library_service", fromlist=["Library"]).Library

HERE = Path(__file__).resolve().parent
LEDGER = ROOT / "research/synthetic_data/ledger_chat_dados.json"
QUESTIONS = HERE / "questions_chat_dados.json"
SCHEMA = HERE / "questions_chat_dados.schema.json"
MANIFEST = HERE / "chat_dados_manifest.json"


def load_library() -> Library:
    data = json.loads(LEDGER.read_text())
    return Library(
        transactions=[Transaction(**tx) for tx in data["transactions"]],
        accounts={a["id"]: Account(**a) for a in data["accounts"]},
        statements={s["id"]: Statement(**s) for s in data["statements"]},
    )


def expected_values(recipe: dict, library: Library) -> list[dict]:
    if recipe["kind"] == "none":
        return []
    txs = [
        tx
        for tx in library.transactions
        if (not recipe.get("account") or tx.account_id == recipe["account"])
        and (not recipe.get("owner") or library.accounts[tx.account_id].owner == recipe["owner"])
        and (not recipe.get("month") or tx.date.strftime("%Y-%m") == recipe["month"])
    ]
    kind = recipe["kind"]
    if kind == "comparison":
        return [
            {
                "key": key,
                "value": CalculationService.calculate_summary(
                    [tx for tx in txs if tx.date.strftime("%Y-%m") == month]
                ).total_expenses,
                "unit": "BRL",
            }
            for key, month in zip(
                ("compare_first", "compare_second"), recipe["months"], strict=True
            )
        ]
    if kind in {"installments", "debt"}:
        if kind == "installments":
            latest = max((tx for tx in txs if tx.installment_number), key=lambda tx: tx.date)
            txs = [
                latest.model_copy(update={"id": f"future-{i}"})
                for i in range(latest.installment_total - latest.installment_number)
            ]
            key = "installments_remaining"
        else:
            closed = max(
                (
                    s
                    for s in library.statements.values()
                    if s.account_id == "sintetica-card" and s.status == "fechada"
                ),
                key=lambda s: s.period_end,
            )
            txs = [tx for tx in txs if tx.statement_id == closed.id]
            key = "closed_statement_due"
        return [
            {
                "key": key,
                "value": CalculationService.calculate_summary(txs).total_expenses,
                "unit": "BRL",
            }
        ]
    summary = CalculationService.calculate_summary(txs)
    if kind == "statement":
        return [{"key": recipe["key"], "value": summary.total_expenses, "unit": "BRL"}]
    return [
        {"key": key, "value": getattr(summary, key), "unit": "BRL"}
        for key in ("total_expenses", "total_income", "net_balance")
    ]


def manifest() -> dict:
    files = [
        LEDGER,
        QUESTIONS,
        SCHEMA,
        Path(__file__).resolve(),
        ROOT / "research/synthetic_data/generate_chat_dados.py",
        HERE / "run_chat_dados.py",
    ]
    return {
        "schema_version": 1,
        "hash_algorithm": "sha256-bytes",
        "files": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)
        },
    }


def validate() -> list[dict]:
    questions = json.loads(QUESTIONS.read_text())
    Draft202012Validator(json.loads(SCHEMA.read_text())).validate(questions)
    if len({q["id"] for q in questions}) != 20:
        raise ValueError("São necessários vinte identificadores únicos.")
    library = load_library()
    for question in questions:
        if question["expected"] != expected_values(question["recipe"], library):
            raise ValueError(f"Gabarito divergente: {question['id']}")
    if json.loads(MANIFEST.read_text()) != manifest():
        raise ValueError("Manifesto divergente.")
    return questions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        questions = json.loads(QUESTIONS.read_text())
        for question in questions:
            question["expected"] = expected_values(question["recipe"], load_library())
        QUESTIONS.write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n")
        MANIFEST.write_text(json.dumps(manifest(), ensure_ascii=False, indent=2) + "\n")
    print(f"{len(validate())} cenários válidos; gabarito e hashes conferidos.")


if __name__ == "__main__":
    main()
