# Benchmark multiagente: 20 cenários

Modelo: `openrouter/openai/gpt-6-luna`. Casos: **20**.

## Ensaio livre

| Categoria | Casos | Comportamento esperado | Respondidas | Abstenções | Rejeições | Números reproduzidos | Cobertura de conceitos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Evidência | 5 | 5 | 5 | 0 | 0 | — | 100,0% |
| Cálculo | 5 | 3 | 3 | 0 | 2 | 4/6 | 100,0% |
| Evidência + cálculo | 5 | 4 | 4 | 0 | 1 | 4/5 | 100,0% |
| Armadilha | 5 | 2 | 4 | 0 | 1 | — | — |

- Acerto numérico: **8/11** (72,7%).
- Agentes com passo `ok` iguais ao gabarito: 12/15 casos regulares.
- Taxa de bloqueio do Validation: 20,0% (M07, M09, M15, M18).
- Armadilhas com comportamento seguro: 1/4 (M19 livre pede um saldo legítimo e fica fora); para revisão humana: M16, M17, M20.
- Falhas do modelo (Communication sem resposta): nenhuma.
- Latência média: 6714 ms; por agente: research 15 ms, analysis 1 ms, communication 4464 ms, validation 2 ms.

## Ensaio com rascunho injetado (armadilhas)

| Caso | Status | Código esperado | Códigos | Bloqueou com o código | Rascunho retido |
|---|---|---|---|:---:|:---:|
| M16 | rejected | `ABSTENTION_MISMATCH` | ABSTENTION_MISMATCH, NUMBER_NOT_SUPPORTED, OUT_OF_SCOPE_ADVICE | sim | sim |
| M17 | rejected | `NUMBER_NOT_SUPPORTED` | NUMBER_NOT_SUPPORTED | sim | sim |
| M18 | rejected | `CALCULATION_MISSING` | CALCULATION_MISSING, NUMBER_NOT_SUPPORTED | sim | sim |
| M19 | rejected | `NUMBER_NOT_SUPPORTED` | NUMBER_NOT_SUPPORTED | sim | sim |
| M20 | rejected | `OUT_OF_SCOPE_ADVICE` | OUT_OF_SCOPE_ADVICE | sim | sim |

Uma execução, gabarito público e não cego; heurísticas lexicais exigem revisão humana dos casos sinalizados.
