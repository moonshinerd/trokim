# Analysis Agent

!!! info "Status: Planejado"
    Issue [#53](https://github.com/moonshinerd/trokim/issues/53). Esta página é preenchida no mesmo PR da implementação (regra: o MkDocs nunca fica defasado).

Faz **todo cálculo** de uma pergunta numérica por código, para que o modelo só explique números prontos
([ADR 0004](../adr/0004-calculos-deterministicos.md)). Resolve na raiz as falhas C29 (percentuais
inventados) e C30 (cálculo sem resultado do sistema). Não usa modelo de linguagem.

## Intenções previstas

| Intenção | O que calcula | Base |
|---|---|---|
| Resumo | Receitas, despesas, saldo e taxa de poupança | `CalculationService.calculate_summary` |
| Categorias | Despesa por categoria e participação no total | `category_shares` (novo) |
| Meta | Meses para juntar um valor poupando um aporte mensal | `months_to_goal` (novo) |
| Cenários | Comparação de dois cenários informados | `CalculationService.compare_budget_scenarios` |

Sem lançamentos importados, ou com uma pergunta numérica que o agente não sabe calcular, o passo é
`skipped` e as premissas dizem **o que falta**; o Communication Agent deve repetir isso, nunca estimar.

## Como funciona na prática
*(A preencher: tabela de palavras-chave, fórmulas e exemplos numéricos reais com o extrato sintético.)*

## Limitações
*(A preencher.)*
