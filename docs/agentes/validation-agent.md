# Validation Agent

!!! info "Status: Planejado"
    Issue [#54](https://github.com/moonshinerd/trokim/issues/54). Esta página é preenchida no mesmo PR da implementação (regra: o MkDocs nunca fica defasado).

Garante que **nenhuma resposta saia sem uma checagem independente e determinística** do rascunho.
Reaproveita as ideias do avaliador da Semana 3, dentro da API. Não usa modelo de linguagem.

## Regras previstas

| Código | Severidade | Quando |
|---|---|---|
| `NUMBER_NOT_SUPPORTED` | Bloqueio | Número no rascunho que não está nos cálculos nem nas evidências |
| `CITATION_INVALID` | Bloqueio | Marcador `[n]` sem evidência correspondente, ou resposta com evidências e nenhuma citação |
| `OUT_OF_SCOPE_ADVICE` | Bloqueio | Recomendação de produto ou ação específica, promessa de rendimento |
| `ABSTENTION_MISMATCH` | Bloqueio | Respondeu apesar de haver motivo de abstenção |
| `CALCULATION_MISSING` | Bloqueio | Pergunta numérica sem cálculos e rascunho com resultado numérico próprio |

## Casos de regressão da Semana 3
C27 (previsão de preço), C29 (percentual não fornecido), C30 (resultado calculado sem o sistema), C04 e C17 (valores inventados).

## Como funciona na prática
*(A preencher: extração de números em pt-BR, exemplos reais e taxa de falso positivo medida.)*

## Limitações
*(A preencher.)*
