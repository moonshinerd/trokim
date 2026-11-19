"""Atividade econômica (CNAE 2.3, IBGE/CONCLA) → categoria de gasto do Trokim.

Usada quando o extrato traz o CNPJ do recebedor e as regras por palavra não reconhecem o nome
(ver ``cnpj_index``). Vale o prefixo mais longo: subclasse (7 dígitos), classe (4), grupo (3) ou
divisão (2). O que não está aqui fica em ``outros``: indústria, atacado e agro não dizem nada
sobre o gasto de uma pessoa.

Convenções iguais às das regras por palavra (``docs/arquitetura/categorias.md``): varejo em
geral fica em ``servicos``; viagem, hospedagem e pet em ``lazer``; academia em ``saude``;
administração pública em ``impostos`` (só para saídas).
"""

from app.domain.models import TransactionCategory as C

_PREFIXES: dict[str, C] = {
    # Alimentação: fabricação artesanal (padarias registradas como indústria), mercados,
    # padarias, açougues, bebidas, hortifrúti, restaurantes e lanchonetes.
    "10": C.FOOD,
    "11": C.FOOD,
    "4711": C.FOOD,
    "4712": C.FOOD,
    "4721": C.FOOD,
    "4722": C.FOOD,
    "4723": C.FOOD,
    "4724": C.FOOD,
    "4729": C.FOOD,
    "56": C.FOOD,
    # Transporte: veículos, oficinas, combustível, passageiros, pedágio e estacionamento.
    "4511": C.TRANSPORT,
    "4520": C.TRANSPORT,
    "4530": C.TRANSPORT,
    "4541": C.TRANSPORT,
    "4543": C.TRANSPORT,
    "4731": C.TRANSPORT,
    "4732": C.TRANSPORT,
    "4912": C.TRANSPORT,
    "492": C.TRANSPORT,
    "4950": C.LEISURE,
    "5221": C.TRANSPORT,
    "5222": C.TRANSPORT,
    "5223": C.TRANSPORT,
    "5229": C.TRANSPORT,
    "7711": C.TRANSPORT,
    # Moradia: energia, água, gás de cozinha, obra, material de construção, móveis,
    # imobiliárias e condomínios.
    "35": C.HOUSING,
    "36": C.HOUSING,
    "37": C.HOUSING,
    "4784": C.HOUSING,
    "41": C.HOUSING,
    "43": C.HOUSING,
    "4741": C.HOUSING,
    "4742": C.HOUSING,
    "4743": C.HOUSING,
    "4744": C.HOUSING,
    "4754": C.HOUSING,
    "4759": C.HOUSING,
    "68": C.HOUSING,
    "8112": C.HOUSING,
    # Saúde: farmácias, artigos médicos, ótica, planos, hospitais, clínicas e academias.
    "4771": C.HEALTH,
    "4773": C.HEALTH,
    "4774": C.HEALTH,
    "6550": C.HEALTH,
    "86": C.HEALTH,
    "87": C.HEALTH,
    "9313": C.HEALTH,
    # Educação: escolas, faculdades, cursos e livrarias.
    "85": C.EDUCATION,
    "4761": C.EDUCATION,
    # Lazer: viagem, hospedagem, cultura, esporte, jogos, brinquedos e pet.
    "51": C.LEISURE,
    "55": C.LEISURE,
    "79": C.LEISURE,
    "5914": C.LEISURE,
    "90": C.LEISURE,
    "91": C.LEISURE,
    "92": C.LEISURE,
    "93": C.LEISURE,
    "4762": C.LEISURE,
    "4763": C.LEISURE,
    "4789004": C.LEISURE,  # animais de estimação, rações e artigos
    "75": C.LEISURE,  # veterinária (pet, como nas regras por palavra)
    "772": C.LEISURE,
    # Serviços: varejo em geral, telecom, internet e software, bancos, seguros, profissionais
    # liberais, locações, reparos, beleza e lavanderia.
    "4713": C.SERVICES,
    "4751": C.SERVICES,
    "4752": C.SERVICES,
    "4753": C.SERVICES,
    "4755": C.SERVICES,
    "4756": C.SERVICES,
    "4757": C.SERVICES,
    "4772": C.SERVICES,
    "478": C.SERVICES,
    "53": C.SERVICES,
    "58": C.SERVICES,
    "60": C.SERVICES,
    "61": C.SERVICES,
    "62": C.SERVICES,
    "63": C.SERVICES,
    "64": C.SERVICES,
    "65": C.SERVICES,
    "66": C.SERVICES,
    "69": C.SERVICES,
    "71": C.SERVICES,
    "73": C.SERVICES,
    "74": C.SERVICES,
    "773": C.SERVICES,
    "78": C.SERVICES,
    "80": C.SERVICES,
    "81": C.SERVICES,
    "82": C.SERVICES,
    "95": C.SERVICES,
    "96": C.SERVICES,
    "97": C.SERVICES,
    # Impostos e taxas: administração pública (prefeitura, Detran, Receita).
    "84": C.TAXES,
}


def category_for_cnae(cnae: str | int | None) -> C:
    """Categoria da subclasse CNAE (com ou sem pontuação); ``outros`` quando não há regra."""
    if cnae is None:
        return C.OTHER
    digits = "".join(ch for ch in str(cnae) if ch.isdigit()).zfill(7)[:7]
    for size in (7, 5, 4, 3, 2):
        category = _PREFIXES.get(digits[:size])
        if category is not None:
            return category
    return C.OTHER
