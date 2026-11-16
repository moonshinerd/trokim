# Communication Agent

!!! info "Status: Planejado"
    Issue [#55](https://github.com/moonshinerd/trokim/issues/55). Esta página é preenchida no mesmo PR da implementação (regra: o MkDocs nunca fica defasado).

Escreve, em pt-BR e em tom pedagógico, a resposta final **somente a partir** das evidências numeradas e
dos cálculos recebidos. É o **único agente que usa LLM** (porta `LLMProvider`, [ADR 0009](../adr/0009-sintese-generativa-local.md)).

## Regras do prompt previstas (`prompt_agente_comunicacao_v1.txt`)
- Usar só as evidências `[1]`, `[2]`... e os resultados de cálculo fornecidos; citar cada afirmação de fonte.
- Não calcular nem estimar; se faltar dado, dizer exatamente o que falta.
- Não recomendar produto ou ação específica.
- Em revisão (volta da Validation), receber os problemas encontrados e corrigi-los.

## Como funciona na prática
*(A preencher: exemplos reais de pergunta, evidências e resposta, e a validação com o modelo local.)*

## Limitações
*(A preencher: limites do modelo de 1,5 B.)*
