"""Confere um arquivo REAL de banco, no seu computador, e imprime só números agregados.

Uso: ``make validar-banco ARQUIVO=/caminho/do/arquivo``. Serve para decidir se um banco
``experimental`` pode virar ``validado`` (ADR 0022): o leitor reconheceu o banco? o total do
arquivo fecha com a soma dos lançamentos? Nada é enviado para fora e **nada que identifique
alguém é impresso**: sem descrições, sem nomes, sem número de conta (só os 4 últimos dígitos).
Não grave a saída no repositório junto com o arquivo original.
"""

import sys
from collections import Counter
from pathlib import Path

from app.services.bank_registry import get_bank
from app.services.parser_service import OfxParseResult, ParserService
from app.services.pdf_profiles import parse_statement_file


def brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def load(path: Path) -> OfxParseResult | None:
    content = path.read_bytes()
    if path.suffix.lower() == ".ofx":
        return ParserService.parse_ofx_detailed(content, path.name)
    return parse_statement_file(content, path.name)


def summarize(parsed: OfxParseResult) -> list[str]:
    txs = parsed.transactions
    debit = round(sum(t.amount for t in txs if t.type.value == "debit"), 2)
    credit = round(sum(t.amount for t in txs if t.type.value == "credit"), 2)
    bank = get_bank(parsed.institution)
    acct = (parsed.meta.acct_id if parsed.meta else None) or ""
    start = parsed.meta.period_start if parsed.meta else None
    before = sum(1 for t in txs if start and t.date < start)
    lines = [
        f"banco reconhecido : {bank.display_name if bank else parsed.institution} "
        f"({bank.support_level if bank else 'fora do registro'})",
        f"tipo              : {parsed.kind or 'desconhecido'}",
        f"conta             : ...{acct[-4:]}" if acct else "conta             : (sem número)",
        f"lançamentos       : {len(txs)}",
        f"período           : {parsed.meta.period_start if parsed.meta else '?'} a "
        f"{parsed.meta.period_end if parsed.meta else '?'}",
        f"soma de débitos   : {brl(debit)}",
        f"soma de créditos  : {brl(credit)}",
        f"parcelados        : {sum(1 for t in txs if t.installment_total)}",
        f"datas fora do período: {before}",
    ]
    natures = Counter(t.nature.value for t in txs)
    lines.append("naturezas         : " + ", ".join(f"{k}={v}" for k, v in sorted(natures.items())))
    outros = natures.get("outro", 0)
    if txs and outros / len(txs) > 0.3:
        lines.append(f"ATENÇÃO: {outros} de {len(txs)} lançamentos ficaram como 'outro'")
    rec = parsed.reconciled
    lines.append(
        "total do arquivo  : "
        + (
            "FECHA com a soma"
            if rec is True
            else "NÃO FECHA"
            if rec is False
            else "arquivo sem total"
        )
    )
    return lines


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: validar_banco.py <arquivo .ofx | .pdf | .csv>")
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"arquivo não encontrado: {path.name}")
        return 2
    try:
        parsed = load(path)
    except Exception as exc:  # o texto do erro pode ter trechos do arquivo: só o tipo
        print(f"não consegui ler o arquivo ({type(exc).__name__}).")
        return 1
    if parsed is None or not parsed.transactions:
        print("nenhum perfil reconheceu este arquivo: o banco continua sem suporte nesse formato.")
        return 1
    print("\n".join(summarize(parsed)))
    ok = parsed.reconciled is not False and bool(parsed.transactions)
    print(
        "\nresultado         : " + ("OK para conferir contra o app do banco" if ok else "REPROVADO")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
