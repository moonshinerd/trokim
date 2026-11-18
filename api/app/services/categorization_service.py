"""Categorização determinística de lançamentos por estabelecimento.

As regras casam por **palavra inteira** (sem acento e sem diferenciar caixa),
em ordem de prioridade. Isso evita erros de trecho, como ``gas`` dentro de
``drogasil`` ou ``uber`` em ``uber eats``. A LLM nunca categoriza: ela só poderá
sugerir no app, e quem decide é o usuário.
"""

import re

from app.domain.models import (
    TransactionCategory,
    TransactionNature,
    TransactionType,
)
from app.services.statement_profiles import normalize_text

C = TransactionCategory

# Ordem importa: a primeira regra que casar vence (mais específicas primeiro).
_RULES: list[tuple[TransactionCategory, tuple[str, ...]]] = [
    (C.FOOD, ("uber eats", "ifood", "99food", "99 food", "rappi", "aiqfome", "ze delivery")),
    (
        C.HEALTH,
        (
            "drogasil",
            "drogaria",
            "droga raia",
            "pacheco",
            "farmacia",
            "medico",
            "hospital",
            "clinica",
            "dentista",
            "laboratorio",
            "totalpass",
            "smartfit",
            "academia",
            "amil",
            "unimed",
            "plano de saude",
        ),
    ),
    (
        C.TRANSPORT,
        (
            "uber",
            "99",
            "99pop",
            "cabify",
            "combustivel",
            "posto",
            "ipiranga",
            "onibus",
            "metro",
            "bilhete unico",
            "estacionamento",
            "patinete",
            "patinetes",
            "pedagio",
            "sem parar",
        ),
    ),
    (
        C.HOUSING,
        (
            "aluguel",
            "condominio",
            "energia",
            "luz",
            "agua",
            "gas",
            "internet",
            "iptu",
            "enel",
            "cemig",
            "sabesp",
        ),
    ),
    (C.EDUCATION, ("curso", "faculdade", "escola", "livraria", "udemy", "alura", "mensalidade")),
    (
        C.LEISURE,
        (
            "cinema",
            "netflix",
            "spotify",
            "viagem",
            "steam",
            "disney",
            "hbo",
            "prime video",
            "amazon prime",
            "youtube",
            "playstation",
            "xbox",
            "bar",
            "pub",
            "balada",
            "show",
            "ingresso",
            "sympla",
            "tattoo",
            "piercing",
            "easyjet",
            "latam",
            "decolar",
            "hotel",
            "booking",
            "airbnb",
        ),
    ),
    (
        C.FOOD,
        (
            "mercado",
            "supermercado",
            "supermercados",
            "padaria",
            "restaurante",
            "lanchonete",
            "lanches",
            "lanche",
            "adega",
            "acougue",
            "hortifruti",
            "carrefour",
            "atacadao",
            "assai",
            "pao de acucar",
            "sorveteria",
            "pizzaria",
            "cafe",
            "cafeteria",
            "mercadinho",
            "emporio",
            "doceria",
            "burger king",
            "mcdonalds",
            "arcos dourados",
            "panificadora",
            "confeit",
            "confeitaria",
            "bk brasil",
            "habibs",
            "subway",
            "outback",
        ),
    ),
    (
        C.SERVICES,
        (
            "mercado livre",
            "mercadolivre",
            "amazon",
            "shopee",
            "aliexpress",
            "magalu",
            "americanas",
            "nupay",
            "assinatura",
            "seguro",
            "tarifa",
            "anuidade",
            "barbearia",
            "salao",
            "lavanderia",
            "pagtesouro",
            "espaco feminino",
        ),
    ),
    (C.INCOME, ("salario", "proventos", "pagamento de salario", "ted recebida", "rendimento")),
]

# "mercado livre" é serviço de compras, e não alimentação: vence "mercado" se vier antes.
_PRIORITY_FIRST = ("mercado livre", "mercadolivre")

_EXCLUDED = {
    TransactionNature.CARD_PAYMENT,
    TransactionNature.INVESTMENT_APPLY,
    TransactionNature.INVESTMENT_REDEEM,
    TransactionNature.INTERNAL_TRANSFER,
}


def _contains_phrase(normalized: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", normalized) is not None


class CategorizationService:
    @staticmethod
    def categorize(
        text: str,
        *,
        tx_type: TransactionType | None = None,
        nature: TransactionNature = TransactionNature.OTHER,
    ) -> TransactionCategory:
        if nature in _EXCLUDED:
            return C.OTHER
        normalized = normalize_text(text)
        if any(_contains_phrase(normalized, phrase) for phrase in _PRIORITY_FIRST):
            return C.SERVICES
        for category, phrases in _RULES:
            if category == C.INCOME and tx_type == TransactionType.DEBIT:
                continue
            if any(_contains_phrase(normalized, phrase) for phrase in phrases):
                return category
        if tx_type == TransactionType.CREDIT and nature in {
            TransactionNature.PIX_IN,
            TransactionNature.OTHER,
        }:
            return C.INCOME
        return C.OTHER
