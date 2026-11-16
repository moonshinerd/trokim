# Research Agent

!!! info "Status: Planejado"
    Issue [#52](https://github.com/moonshinerd/trokim/issues/52). Esta página é preenchida no mesmo PR da implementação (regra: o MkDocs nunca fica defasado).

Encapsula a recuperação de evidências oficiais e a política de escopo e abstenção do `RAGService`
como um agente. É a primeira linha de defesa: o que estiver fora de escopo ou sem evidência
**nunca chega ao LLM**. Não usa modelo de linguagem.

## Comportamento previsto

| Situação | Resultado |
|---|---|
| Pergunta fora de escopo (apostas, ação específica, criptoativos) | `abstain_reason = "fora_de_escopo"`, passo `abstained` |
| Nenhuma evidência acima do limiar | `abstain_reason = "sem_evidencia"`, passo `abstained` |
| Evidências encontradas | `ctx.evidences` preenchido, passo `ok`; `detail` traz `top_k`, `threshold`, `scores` e `documents` |

## Como funciona na prática
*(A preencher: exemplos reais, incluindo o caso C28 do gabarito da Semana 3.)*

## Limitações
*(A preencher.)*
