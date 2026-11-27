import json
import random
from pathlib import Path

SEED = 981127
OUTPUT = Path(__file__).with_name("ledger_chat_dados.json")


def generate() -> dict:
    rng = random.Random(SEED)
    accounts = [
        {"id": aid, "acct_id": aid, "institution": bank, "kind": kind, "owner": owner}
        for aid, bank, kind, owner in [
            ("sintetica-pf", "nubank", "conta", "pessoal"),
            ("sintetica-pj", "banco_do_brasil", "conta", "empresa"),
            ("sintetica-card", "nubank", "cartao", "pessoal"),
        ]
    ]
    transactions, statements = [], []
    for month in (9, 10, 11):
        for account in accounts:
            aid = account["id"]
            sid = f"{aid}-2026-{month:02}"
            card = account["kind"] == "cartao"
            end = 30 if month in (9, 11) else 31
            statements.append(
                {
                    "id": sid,
                    "account_id": aid,
                    "filename": f"{sid}.sintetico",
                    "kind": account["kind"],
                    "period_start": f"2026-{month:02}-01",
                    "period_end": f"2026-{month:02}-{end}",
                    "status": "aberta" if card and month == 11 else "fechada",
                    "closes_on": f"2026-{month:02}-{end}" if card else None,
                }
            )
            rows = [
                (
                    "Mercado Sintético",
                    rng.randint(25000, 50000) / 100,
                    "debit",
                    "alimentacao",
                    "compra",
                )
            ]
            if not card:
                rows += [
                    (
                        "Receita Sintética",
                        rng.randint(500000, 900000) / 100,
                        "credit",
                        "renda",
                        "outro",
                    ),
                    (
                        "Serviço Sintético",
                        rng.randint(5000, 15000) / 100,
                        "debit",
                        "servicos",
                        "compra",
                    ),
                    ("Transferência Sintética", 723.45, "debit", "outros", "transferencia_propria"),
                ]
            else:
                rows += [("Curso Sintético", 187.35, "debit", "educacao", "compra")]
            for index, (merchant, amount, kind, category, nature) in enumerate(rows):
                tx = {
                    "id": f"{sid}-{index}",
                    "account_id": aid,
                    "statement_id": sid,
                    "description": merchant,
                    "merchant": merchant,
                    "amount": amount,
                    "date": f"2026-{month:02}-{5 + index:02}",
                    "type": kind,
                    "category": category,
                    "nature": nature,
                    "source_kind": account["kind"],
                }
                if merchant == "Curso Sintético":
                    tx.update(installment_number=month - 8, installment_total=8)
                transactions.append(tx)
    return {
        "schema_version": 1,
        "synthetic": True,
        "seed": SEED,
        "months": ["2026-09", "2026-10", "2026-11"],
        "accounts": accounts,
        "statements": statements,
        "transactions": transactions,
    }


def main() -> None:
    OUTPUT.write_text(json.dumps(generate(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
