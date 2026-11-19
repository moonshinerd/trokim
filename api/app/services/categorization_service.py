"""Categorização determinística de lançamentos por estabelecimento.

As regras casam por **palavra inteira** (sem acento e sem diferenciar caixa),
em ordem de prioridade. Isso evita erros de trecho, como ``gas`` dentro de
``drogasil`` ou ``uber`` em ``uber eats``. A LLM nunca categoriza: ela só poderá
sugerir no app, e quem decide é o usuário.
"""

import json
import re
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path

from app.domain.models import (
    Transaction,
    TransactionCategory,
    TransactionNature,
    TransactionType,
)
from app.services.library_service import Library
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
            "paes",
            "conveniencia",
            "acai",
            "hamburgueria",
            "churrascaria",
            "sushi",
            "temakeria",
            "pastelaria",
            "pastel",
            "sacolao",
            "quitanda",
            "rotisseria",
            "cantina",
            "bistro",
            "petiscaria",
            "sorvetes",
            "bebidas",
        ),
    ),
    (
        C.SERVICES,
        (
            "mercado livre",
            "mercadolivre",
            "mercadoliv",
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
    (
        C.TAXES,
        (
            "receita federal",
            "darf",
            "simples nacional",
            "das mei",
            "pgmei",
            "detran",
            "ipva",
            "iptu",
            "sefaz",
            "secretaria da fazenda",
            "prefeitura",
            "inss",
            "dpvat",
            "licenciamento",
        ),
    ),
    (C.INCOME, ("salario", "proventos", "pagamento de salario", "ted recebida", "rendimento")),
]

# Termos que cobrem variações comuns entre bancos e adquirentes (redes nacionais, contas de
# consumo de vários estados, varejo e assinaturas). Só nomes públicos de empresas e palavras do
# ramo; nunca nomes de pessoas. Medido em ``tests/data/categorizacao_variacoes.py``.
_EXTRA: dict[TransactionCategory, tuple[str, ...]] = {
    C.HEALTH: (
        "pague menos",
        "panvel",
        "ultrafarma",
        "drogal",
        "nissei",
        "venancio",
        "farma",
        "consultorio",
        "odonto",
        "odontologia",
        "hapvida",
        "notredame",
        "sulamerica saude",
        "bradesco saude",
        "smart fit",
        "bluefit",
        "selfit",
        "wellhub",
        "gympass",
        "totalpass",
        "total pass",
        "bodytech",
        "bio ritmo",
        "bioritmo",
        "just fit",
        "justfit",
        "pratique fitness",
        "skyfit",
        "sky fit",
        "panobianco",
        "fitness",
        "crossfit",
        "pilates",
        "otica",
        "oticas",
        "psicologa",
        "psicologo",
        "psicologia",
        "fisioterapia",
        "nutricionista",
        "exame",
        "exames",
        "dermatologia",
        "pilates",
        "crossfit",
    ),
    C.TRANSPORT: (
        "99app",
        "99ride",
        "99pop",
        "indrive",
        "shell",
        "petrobras",
        "ale combustiveis",
        "combustiveis",
        "conectcar",
        "veloe",
        "move mais",
        "estapar",
        "zul",
        "brt",
        "oficina",
        "mecanica",
        "auto pecas",
        "autopecas",
        "pecas",
        "borracharia",
        "pneus",
        "lava jato",
        "lava rapido",
        "autocenter",
        "taxi",
        "blablacar",
        "buser",
        "rodoviaria",
        "passagem onibus",
        "clickbus",
    ),
    C.HOUSING: (
        "eletricidade",
        "neoenergia",
        "coelba",
        "celpe",
        "cosern",
        "copel",
        "celesc",
        "rge",
        "elektro",
        "energisa",
        "light sesa",
        "caesb",
        "copasa",
        "cedae",
        "saneago",
        "embasa",
        "compesa",
        "cagece",
        "sanepar",
        "corsan",
        "casan",
        "agua e esgoto",
        "saneamento",
        "comgas",
        "naturgy",
        "ultragaz",
        "liquigas",
        "supergasbras",
        "nacional gas",
        "vivo fibra",
        "claro net",
        "net virtua",
        "net servicos",
        "oi fibra",
        "tim live",
        "sky",
        "desktop fibra",
        "leroy merlin",
        "telha norte",
        "construcao",
        "materiais de construcao",
        "home center",
        "quintoandar",
        "imobiliaria",
        "tok stok",
        "etna",
        "mobly",
    ),
    C.EDUCATION: (
        "coursera",
        "duolingo",
        "universidade",
        "colegio",
        "kalunga",
        "papelaria",
        "idiomas",
        "wizard",
        "ccaa",
        "fisk",
        "cultura inglesa",
        "kumon",
        "descomplica",
        "estrategia concursos",
        "hotmart",
        "domestika",
        "livros",
        "saraiva",
        "amazon kindle",
        "kindle",
    ),
    C.LEISURE: (
        "hbomax",
        "hbo max",
        "streaming",
        "globoplay",
        "deezer",
        "crunchyroll",
        "paramount",
        "apple tv",
        "star plus",
        "telecine",
        "steamgames",
        "nintendo",
        "epic games",
        "riot games",
        "blizzard",
        "cinemark",
        "cinepolis",
        "kinoplex",
        "uci",
        "eventim",
        "ticketmaster",
        "teatro",
        "museu",
        "parque",
        "choperia",
        "chopp",
        "cervejaria",
        "boteco",
        "pousada",
        "resort",
        "linhas aereas",
        "smiles",
        "123milhas",
        "milhas",
        "hurb",
        "cvc",
        "pet shop",
        "petshop",
        "petz",
        "cobasi",
        "petlove",
        "veterinaria",
        "veterinario",
        "clube",
    ),
    C.FOOD: (
        "extra",
        "hiper",
        "hipermercado",
        "minimercado",
        "minimercados",
        "sams club",
        "makro",
        "atacadista",
        "atacado",
        "mercearia",
        "frigorifico",
        "carnes",
        "casa de carnes",
        "oxxo",
        "starbucks",
        "spoleto",
        "kopenhagen",
        "chocolates",
        "bobs",
        "giraffas",
        "china in box",
        "kfc",
        "popeyes",
        "dominos",
        "pizza hut",
        "madero",
        "coco bambu",
        "ragazzo",
        "jeronimo",
        "lanches",
        "lanchonete",
        "hortifruit",
        "feira",
        "dogueria",
        "creperia",
        "tapiocaria",
        "food",
        "foods",
        "doces",
        "salgados",
        "marmitaria",
        "comida",
        "gastronomia",
        "grill",
        "steakhouse",
        "burguer",
        "burger",
    ),
    C.SERVICES: (
        "shein",
        "magazine luiza",
        "casas bahia",
        "ponto frio",
        "kabum",
        "renner",
        "riachuelo",
        "c a modas",
        "cea modas",
        "centauro",
        "decathlon",
        "netshoes",
        "dafiti",
        "zara",
        "hering",
        "marisa",
        "pernambucanas",
        "boticario",
        "natura",
        "avon",
        "sephora",
        "apple",
        "google",
        "microsoft",
        "chatgpt",
        "openai",
        "canva",
        "dropbox",
        "adobe",
        "icloud",
        "recarga",
        "pre pago",
        "celular",
        "correios",
        "chaveiro",
        "espaco laser",
        "cesta de servicos",
        "manicure",
        "estetica",
        "costureira",
        "grafica",
        "copiadora",
        "cartorio",
        "despachante",
        "contabilidade",
        "advocacia",
        "assistencia tecnica",
        "temu",
        "submarino",
        "fast shop",
        "carrefour com",
        "aliexpress",
    ),
}

# Vencem antes de tudo: nomes que contêm palavra de outra categoria ("show", "aluguel").
_PRIORITY_RULES: list[tuple[TransactionCategory, tuple[str, ...]]] = [
    (C.FOOD, ("cacau show",)),
    (C.TRANSPORT, ("movida", "localiza", "rent a car", "unidas", "aluguel de carro")),
]

_RULES = _PRIORITY_RULES + [
    (category, phrases + _EXTRA.get(category, ())) for category, phrases in _RULES
]

# "mercado livre" é serviço de compras, e não alimentação: vence "mercado" se vier antes.
_PRIORITY_FIRST = ("mercado livre", "mercadolivre", "mercadoliv")

_EXCLUDED = {
    TransactionNature.CARD_PAYMENT,
    TransactionNature.INVESTMENT_APPLY,
    TransactionNature.INVESTMENT_REDEEM,
    TransactionNature.INTERNAL_TRANSFER,
}


def _contains_phrase(normalized: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", normalized) is not None


# Nome colado pelo adquirente ("PAG*LANCHESDAMARIA"): só palavras longas valem como trecho.
_GLUED_TOKEN = 10
_GLUED_PHRASE = 6


def _glued_match(normalized: str, phrases: tuple[str, ...]) -> bool:
    tokens = [t for t in normalized.split() if len(t) >= _GLUED_TOKEN and t.isalpha()]
    if not tokens:
        return False
    return any(
        phrase in token
        for token in tokens
        for phrase in phrases
        if len(phrase) >= _GLUED_PHRASE and " " not in phrase and phrase != token
    )


def _matches(normalized: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(normalized, phrase) for phrase in phrases)


_BRANDS_FILE = Path(__file__).resolve().parents[1] / "data" / "marcas_cnpj.json"


@lru_cache(maxsize=1)
def _brands() -> tuple[dict[str, TransactionCategory], int]:
    """Dicionário de redes gerado dos dados abertos do CNPJ (ADR 0020); vazio se não existir."""
    try:
        data = json.loads(_BRANDS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, 0
    brands = {name: TransactionCategory(cat) for name, cat in data.get("marcas", {}).items()}
    longest = max((len(name.split()) for name in brands), default=0)
    return brands, min(longest, 6)


def _by_brand(normalized: str) -> TransactionCategory | None:
    """Maior sequência de palavras do texto que é o nome de uma rede conhecida."""
    brands, longest = _brands()
    if not brands:
        return None
    tokens = normalized.split()
    for size in range(min(longest, len(tokens)), 0, -1):
        for start in range(len(tokens) - size + 1):
            found = brands.get(" ".join(tokens[start : start + size]))
            if found is not None:
                return found
    return None


class CategorizationService:
    @staticmethod
    def _by_rules(
        normalized: str,
        tx_type: TransactionType | None,
        match: Callable[[str, tuple[str, ...]], bool],
    ) -> TransactionCategory | None:
        for category, phrases in _RULES:
            if category == C.INCOME and tx_type == TransactionType.DEBIT:
                continue
            # Entrada da prefeitura ou do INSS é salário ou benefício, não imposto.
            if category == C.TAXES and tx_type == TransactionType.CREDIT:
                continue
            if match(normalized, phrases):
                return category
        return None

    @staticmethod
    def categorize(
        text: str,
        *,
        tx_type: TransactionType | None = None,
        nature: TransactionNature = TransactionNature.OTHER,
        cnpj: str | None = None,
    ) -> TransactionCategory:
        if nature in _EXCLUDED:
            return C.OTHER
        # Pontuação vira espaço: "UBER *EATS" casa com "uber eats" e "C&A" com "c a".
        normalized = re.sub(r"[^a-z0-9]+", " ", normalize_text(text)).strip()
        if _matches(normalized, _PRIORITY_FIRST):
            return C.SERVICES
        category = CategorizationService._by_rules(normalized, tx_type, _matches)
        if category is None:
            category = CategorizationService._by_rules(normalized, tx_type, _glued_match)
        if category is None and tx_type != TransactionType.CREDIT:
            category = _by_brand(normalized)
        if category is not None:
            return category
        if cnpj and tx_type != TransactionType.CREDIT:
            # Nome desconhecido, mas o banco trouxe o CNPJ: vale a atividade da empresa (CNAE).
            from app.services.cnpj_index import get_index

            index = get_index()
            found = index.lookup(cnpj) if index else None
            if found is not None:
                return found
        if tx_type == TransactionType.CREDIT and nature in {
            TransactionNature.PIX_IN,
            TransactionNature.OTHER,
        }:
            return C.INCOME
        return C.OTHER


# Gastos e entradas que o usuário pode recategorizar: movimentações internas não têm categoria.
def can_recategorize(tx: Transaction) -> bool:
    return tx.nature not in _EXCLUDED and not tx.is_duplicate


def merchant_key(merchant: str | None) -> str | None:
    """Chave da regra aprendida: o estabelecimento normalizado (sem acento e sem caixa)."""
    if not merchant:
        return None
    key = " ".join(normalize_text(merchant).split())
    return key if len(key) >= 3 else None


class CategoryRuleService:
    """Regras de categoria aprendidas com o usuário (sempre locais, sem LLM)."""

    @staticmethod
    def apply(library: Library, txs: Iterable[Transaction]) -> int:
        """Aplica as regras do usuário aos lançamentos dados. Devolve quantos mudaram."""
        changed = 0
        for tx in txs:
            key = merchant_key(tx.merchant)
            rule = library.category_rules.get(key) if key else None
            if rule is None or not can_recategorize(tx) or tx.uid in library.own_marks:
                continue
            if tx.category != rule:
                tx.category = rule
                changed += 1
        return changed

    @staticmethod
    def set_category(
        library: Library, uid: str, category: TransactionCategory, *, apply_to_merchant: bool = True
    ) -> dict[str, object]:
        tx = next((t for t in library.transactions if t.uid == uid), None)
        if tx is None:
            raise LookupError("Lançamento não encontrado.")
        if not can_recategorize(tx) or tx.uid in library.own_marks:
            raise ValueError(
                "Pagamento de fatura, investimento e transferência entre suas contas não têm "
                "categoria."
            )
        if category == C.INCOME and tx.type == TransactionType.DEBIT:
            raise ValueError("Um gasto não pode ser classificado como renda.")
        tx.category = category
        updated = 1
        key = merchant_key(tx.merchant) if apply_to_merchant else None
        if key:
            library.category_rules[key] = category
            others = [t for t in library.transactions if t.uid != uid]
            updated += CategoryRuleService.apply(library, others)
        return {"updated": updated, "merchant": tx.merchant if key else None, "rule": bool(key)}

    @staticmethod
    def rules(library: Library) -> list[dict[str, str]]:
        return [
            {"merchant": key, "category": category.value}
            for key, category in sorted(library.category_rules.items())
        ]

    @staticmethod
    def remove_rule(library: Library, key: str) -> None:
        normalized = merchant_key(key)
        if normalized not in library.category_rules:
            raise LookupError("Regra não encontrada.")
        del library.category_rules[normalized]
