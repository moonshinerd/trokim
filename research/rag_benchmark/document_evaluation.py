"""Avaliação pura: acerto exato separado de números corretos e erros de transcrição.

Não normaliza nomes para melhorar a métrica nem fornece gabarito ao agente.
"""

from collections import Counter
from decimal import Decimal


def row_signature(row: dict, *, numeric_only: bool = False) -> tuple:
    amount = Decimal(str(row["amount"])) if row["amount"] is not None else None
    numbers = (row["date"], amount, row.get("installment"))
    return numbers if numeric_only else (*numbers, row["description"])


def matched_rows(expected: list[dict], actual: list[dict], *, numeric_only: bool = False) -> int:
    reference = Counter(row_signature(row, numeric_only=numeric_only) for row in expected)
    observed = Counter(row_signature(row, numeric_only=numeric_only) for row in actual)
    return sum((reference & observed).values())


def summarize(cases: list[dict], readings: list[dict]) -> dict:
    truth = {case["id"]: case for case in cases}
    if len(truth) != len(cases) or len({row["id"] for row in readings}) != len(readings):
        raise ValueError("IDs duplicados no gabarito ou nas leituras.")
    if set(truth) != {row["id"] for row in readings}:
        raise ValueError("Leituras devem cobrir exatamente os casos avaliados.")
    result = {}
    for split in ("calibration", "validation"):
        rows = [row for row in readings if truth[row["id"]]["split"] == split]
        gate = dict.fromkeys(
            ("readable_accepted", "readable_rejected", "illegible_accepted", "illegible_rejected"),
            0,
        )
        totals = dict.fromkeys(
            (
                "correct_fields",
                "recoverable_fields",
                "unexpected_fields",
                "wrong_fields",
                "missing_fields",
                "correct_transactions",
                "recoverable_transactions",
                "unmatched_transactions",
                "numeric_transactions",
                "numeric_mismatches",
                "transcription_mismatches",
                "missing_transactions",
                "illegible_documents",
                "safe_abstentions",
                "technical_failures",
            ),
            0,
        )
        per_field = {}
        for row in rows:
            case = truth[row["id"]]
            bad = case["expected_quality"] == "illegible"
            gate[
                ("illegible" if bad else "readable")
                + ("_rejected" if row["gate_rejected"] else "_accepted")
            ] += 1
            if "document" not in row:
                continue
            doc = row["document"]
            totals["technical_failures"] += doc is None
            totals["illegible_documents"] += bad
            totals["safe_abstentions"] += bool(
                bad and doc and doc["abstained"] and not doc["fields"] and not doc["transactions"]
            )
            expected = case["recoverable_fields"]
            actual = {f["key"]: f["value"] for f in doc["fields"]} if doc else {}
            totals["recoverable_fields"] += len(expected)
            totals["unexpected_fields"] += len(actual.keys() - expected.keys())
            for key, value in expected.items():
                correct = actual.get(key) == value
                count = per_field.setdefault(key, {"correct": 0, "expected": 0})
                count["expected"] += 1
                count["correct"] += correct
                totals["correct_fields"] += correct
                totals["missing_fields"] += key not in actual
                totals["wrong_fields"] += key in actual and not correct
            reference = case["recoverable_transactions"]
            observed = doc["transactions"] if doc else []
            exact = matched_rows(reference, observed)
            numeric = matched_rows(reference, observed, numeric_only=True)
            totals["recoverable_transactions"] += len(reference)
            totals["correct_transactions"] += exact
            totals["unmatched_transactions"] += len(observed) - exact
            totals["numeric_transactions"] += numeric
            totals["numeric_mismatches"] += len(observed) - numeric
            totals["transcription_mismatches"] += numeric - exact
            totals["missing_transactions"] += len(reference) - numeric
        measured = any("document" in row for row in rows)
        result[split] = {
            "documents": len(rows),
            "gate": gate,
            **{key: value if measured else None for key, value in totals.items()},
            "per_field": per_field if measured else None,
        }
    return result
