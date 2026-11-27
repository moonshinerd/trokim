"""Classificação determinística das intenções do chat, sem dados da biblioteca."""

import re

from app.domain.agents import FinancialIntent
from app.services.financial_query_service import MONTHS
from app.services.statement_profiles import normalize_text


def requires_guidance(question: str) -> bool:
    return bool(
        re.search(
            r"\b(como|deveria|recomenda\w*|melhor|invest\w*|vale a pena|aposta\w*|bet|"
            r"devo (?:poupar|guardar|fazer)|comprar|vender|garantid\w*|segundo|bcb|cvm)\b",
            normalize_text(question),
        )
    )


def financial_intent(question: str) -> FinancialIntent | None:
    """Prioriza intenções específicas e preserva perguntas conceituais e simulações de meta."""
    text = normalize_text(question)
    if re.match(r"^(?:o que (?:e|sao)|defina|explique o conceito)\b", text):
        return None
    if re.search(r"\b(juntar|meta|objetivo|aporte|poupando)\b", text) or (
        "quanto tempo" in text and not re.search(r"\bparcelas?\b", text)
    ):
        return None
    personal = bool(re.search(r"\b(meu|minha|meus|minhas|gastei|devo|falta pagar)\b", text))
    if requires_guidance(text) and not personal:
        return None
    if re.search(r"gastei (?:mais|menos).*\bou\b", text):
        return FinancialIntent.COMPARISON
    patterns = (
        ("accounts", r"\b(?:cada conta|por conta|minhas contas)\b"),
        ("comparison", r"\b(compar\w*|diferenca|variacao|versus|vs)\b"),
        ("commitments", r"\b(dividas?|compromissos?|venc\w*)\b"),
        ("installments", r"\b(parcelas?|parcelamentos?)\b"),
        ("transfers", r"\b(transferencias?|pagamento de fatura)\b"),
        ("merchants", r"\b(estabelecimentos?|lojas?|onde|comercios?)\b"),
        (
            "categories",
            r"\b(categorias?|alimentacao|moradia|transporte|saude|lazer|educacao|servicos|impostos)\b",
        ),
        ("commitments", r"\b(a pagar|devo|falta pagar)\b"),
        ("statement", r"\b(faturas?|cartao)\b"),
        ("summary", r"\b(saldo|receitas?|despesas?|gastei|gastos?|resumo|balanco|total)\b"),
    )
    intent = next((intent for intent, pattern in patterns if re.search(pattern, text)), None)
    if intent == "comparison" and not re.search(
        r"\b(gastei|gastos?|receitas?|despesas?|saldo|contas?|periodos?|mes)\b|" + "|".join(MONTHS),
        text,
    ):
        return None
    return FinancialIntent(intent) if intent else None
