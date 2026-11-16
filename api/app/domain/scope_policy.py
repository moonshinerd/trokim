"""Política determinística de orientação educacional e abstenção (RF18 / GQ05)."""

import re
import unicodedata

_ASSETS = r"(?:acao|acoes|criptos?|criptomoedas?|criptoativos?)"

# Regras por intenção; menções educativas não são bloqueadas por tema financeiro.
_RULES = tuple(
    re.compile(pattern)
    for pattern in (
        # Pedidos fora do propósito educacional ou de acesso a dados pessoais.
        r"\b(escreva|crie|faca|conte|componha|gere)\b.*\b(poema|poesia|musica|conto|roteiro|piada)\b",
        r"\b(ignore|desconsidere|esqueca)\b.*\b(fontes|regras|instrucoes|diretrizes)\b",
        r"\b(saldo|limite)\b.*\b(minha|meu)\b",
        r"\b(acesse|consulte|revele|mostre)\b.*\b(conta|senha|cpf|extrato)\b",
        r"\b(quanto|qual)\b.*\b(tenho|gastei|recebi)\b",
        # Garantias de retorno e seleção de ativos para compra.
        r"\b(garanta|garantir|prometa|assegure)\b.*\b(lucro|retorno|rendimento|dinheiro)\b",
        r"\b(qual|quais|que)\s+(?:(?:e|sao|seria|seriam)\s+)?"
        r"(?:(?:a|as|o|os)\s+)?(?:melhor(?:es)?\s+)?"
        rf"{_ASSETS}\b.*\b(comprar|compro|investir|invisto|escolher)\b",
        r"\b(diga|indique|escolha|recomende|sugira)\s+"
        rf"(?:(?:um|uma|as|os|a|o|qual|quais|melhor|melhores|me)\s+)*{_ASSETS}\b",
        # Pedidos de aposta ou estratégia, em vez de menções educativas ao tema.
        r"\b(qual|quais|que)\s+(?:(?:a|as|o|os|melhor|melhores)\s+)*"
        r"(apostas?|bets?)\b.*\b(fazer|faco|apostar|ganhar|lucro|rico|dinheiro)\b",
        r"\bcomo\s+(?:(?:posso|devo)\s+)?ganhar\b.*\b(apostas?|bets?)\b",
        r"\b(ensine|crie|monte|indique|recomende|sugira)\b.*"
        r"\b(estrategias?|metodos?|tecnicas?|palpites?)\b.*\b(apostar|apostas?|bets?)\b",
        # Fabricar uma fonte é proibido mesmo sem uma ordem para ignorar regras.
        r"\b(invente|inventar|fabrique|falsifique|forje)\b.*"
        r"\b(resolucao|resolucoes|citacao|citacoes|fontes?|normas?|leis?|"
        r"diretrizes|orientacoes|documentos?|referencias?)\b",
        r"\b(descobrir|roubar|obter|revelar)\b.*\b(senha|cpf)\b",
        r"\b(bolo|futebol|copa do mundo|remedio|gripe|horoscopo)\b",
        r"\b(escreva|gere|crie)\b.*\b(codigo|script|programa)\b",
    )
)


def is_outside_scope(query: str) -> bool:
    """Aplica regras conservadoras; não constitui proteção geral contra ataques."""
    normalized = unicodedata.normalize("NFKD", query).encode("ascii", "ignore").decode().lower()
    normalized = " ".join(normalized.split())
    return any(rule.search(normalized) for rule in _RULES)
