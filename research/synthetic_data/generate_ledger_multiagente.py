"""Gera o extrato sintético fixo do gabarito multiagente (issue #56).

Dados exclusivamente fictícios e determinísticos: a mesma execução produz sempre
o mesmo arquivo. Os totais esperados NÃO ficam aqui; são calculados no teste
pelo CalculationService.

Uso: python research/synthetic_data/generate_ledger_multiagente.py
"""

import json
from pathlib import Path

OUTPUT = Path(__file__).with_name("ledger_multiagente.json")
ACCOUNT = "SINTETICO-MULTIAGENTE"

# (dia, descrição, valor, tipo, categoria)
MESES = {
    "2026-08": [
        (5, "Salário fictício", 5000.00, "credit", "renda"),
        (6, "Aluguel fictício", 1500.00, "debit", "moradia"),
        (8, "Supermercado fictício A", 620.40, "debit", "alimentacao"),
        (15, "Supermercado fictício B", 410.30, "debit", "alimentacao"),
        (10, "Passe de transporte fictício", 220.00, "debit", "transporte"),
        (12, "Farmácia fictícia", 135.90, "debit", "saude"),
        (18, "Cinema fictício", 90.00, "debit", "lazer"),
        (20, "Internet fictícia", 119.90, "debit", "servicos"),
        (22, "Curso online fictício", 180.00, "debit", "educacao"),
    ],
    "2026-09": [
        (5, "Salário fictício", 5000.00, "credit", "renda"),
        (14, "Trabalho avulso fictício", 800.00, "credit", "renda"),
        (6, "Aluguel fictício", 1500.00, "debit", "moradia"),
        (9, "Supermercado fictício A", 598.70, "debit", "alimentacao"),
        (16, "Restaurante fictício", 145.50, "debit", "alimentacao"),
        (10, "Passe de transporte fictício", 220.00, "debit", "transporte"),
        (13, "Consulta fictícia", 250.00, "debit", "saude"),
        (19, "Show fictício", 210.00, "debit", "lazer"),
        (20, "Internet fictícia", 119.90, "debit", "servicos"),
        (22, "Curso online fictício", 180.00, "debit", "educacao"),
    ],
    "2026-10": [
        (5, "Salário fictício", 5000.00, "credit", "renda"),
        (6, "Aluguel fictício", 1500.00, "debit", "moradia"),
        (7, "Supermercado fictício A", 655.10, "debit", "alimentacao"),
        (17, "Supermercado fictício B", 372.00, "debit", "alimentacao"),
        (10, "Passe de transporte fictício", 220.00, "debit", "transporte"),
        (11, "Farmácia fictícia", 88.60, "debit", "saude"),
        (21, "Streaming fictício", 55.90, "debit", "lazer"),
        (20, "Internet fictícia", 119.90, "debit", "servicos"),
        (22, "Curso online fictício", 180.00, "debit", "educacao"),
    ],
}

# Duplicatas (mês, índice do lançamento original): repetem o original e vêm marcadas.
DUPLICATAS = [("2026-08", 2), ("2026-09", 3), ("2026-10", 5)]


def _item(
    mes: str, dia: int, descricao: str, valor: float, tipo: str, categoria: str, duplicata: bool
) -> dict:
    return {
        "id": "",
        "account_id": ACCOUNT,
        "description": descricao,
        "amount": valor,
        "date": f"{mes}-{dia:02d}",
        "type": tipo,
        "category": categoria,
        "is_duplicate": duplicata,
    }


def build() -> dict:
    transactions = []
    for mes, itens in MESES.items():
        for dia, descricao, valor, tipo, categoria in itens:
            transactions.append(_item(mes, dia, descricao, valor, tipo, categoria, False))
        for alvo_mes, alvo_index in DUPLICATAS:
            if alvo_mes == mes:
                dia, descricao, valor, tipo, categoria = itens[alvo_index]
                transactions.append(_item(mes, dia, descricao, valor, tipo, categoria, True))
    for position, tx in enumerate(transactions, start=1):
        tx["id"] = f"LM-{position:03d}"
    return {
        "schema_version": 1,
        "description": "Extrato sintético fixo do gabarito multiagente; nenhum dado real.",
        "transactions": transactions,
    }


def main() -> None:
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extrato escrito em {OUTPUT}")


if __name__ == "__main__":
    main()
