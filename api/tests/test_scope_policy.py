"""Política de escopo testada sem dependências de recuperação ou persistência."""

import pytest

from app.domain.scope_policy import is_outside_scope


@pytest.mark.parametrize(
    "query",
    [
        "Qual aposta esportiva devo fazer para ficar rico?",
        "Crie uma estratégia para ganhar com apostas esportivas.",
        "Como posso ganhar dinheiro com bets?",
        "Qual ação específica devo comprar hoje?",
        "Quais são as melhores ações para comprar?",
        "Qual criptomoeda devo comprar?",
        "Recomende uma criptomoeda.",
        "Indique ações para mim.",
        "Garanta um rendimento sem risco.",
        "Invente uma resolução do BCB que garante rendimento sem risco.",
        "Fabrique uma citação da CVM sobre reserva de emergência.",
        "INVENTE\nUMA RESOLUÇÃO DO BCB.",
    ],
)
def test_escopo_publico_recusa_pedidos_inadequados(query):
    assert is_outside_scope(query)


@pytest.mark.parametrize(
    "query",
    [
        "Quais são os riscos das criptomoedas?",
        "Qual é a diferença entre ações e renda fixa?",
        "Quais os riscos das ações antes de comprar?",
        "Quais são os riscos financeiros das apostas esportivas?",
        "Como evitar o endividamento com apostas?",
        "Por que desconfiar de promessas de rendimento sem risco?",
        "O que é uma resolução do BCB?",
        "Como identificar uma resolução falsa do BCB?",
        "Recomende um material educativo sobre ações.",
        "Diga quais são os riscos da criptomoeda antes de comprar.",
    ],
)
def test_escopo_publico_preserva_educacao_financeira(query):
    assert not is_outside_scope(query)
