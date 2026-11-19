# Benchmark multiagente: 20 cenários

Modelo: `ollama/qwen2.5:1.5b`. Casos: **20**.

## Ensaio livre

| Categoria | Casos | Comportamento esperado | Respondidas | Abstenções | Rejeições | Números reproduzidos | Cobertura de conceitos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Evidência | 5 | 2 | 2 | 0 | 3 | — | 75,0% |
| Cálculo | 5 | 3 | 3 | 0 | 2 | 4/6 | 100,0% |
| Evidência + cálculo | 5 | 1 | 1 | 0 | 4 | 1/5 | 100,0% |
| Armadilha | 5 | 3 | 1 | 1 | 3 | — | — |

- Acerto numérico: **5/11** (45,5%).
- Agentes com passo `ok` iguais ao gabarito: 6/15 casos regulares.
- Taxa de bloqueio do Validation: 20,0% (M09, M12, M15, M17).
- Armadilhas com comportamento seguro: 2/4 (M19 livre pede um saldo legítimo e fica fora); para revisão humana: nenhuma.
- Falhas do modelo (Communication sem resposta): M01, M02, M05, M06, M12, M13, M14, M16, M20.
- Latência média: 64040 ms; por agente: research 70 ms, analysis 1 ms, communication 53307 ms, validation 2 ms.

## Ensaio com rascunho injetado (armadilhas)

| Caso | Status | Código esperado | Códigos | Bloqueou com o código | Rascunho retido |
|---|---|---|---|:---:|:---:|
| M16 | rejected | `ABSTENTION_MISMATCH` | ABSTENTION_MISMATCH, NUMBER_NOT_SUPPORTED, OUT_OF_SCOPE_ADVICE | sim | sim |
| M17 | rejected | `NUMBER_NOT_SUPPORTED` | NUMBER_NOT_SUPPORTED | sim | sim |
| M18 | rejected | `CALCULATION_MISSING` | CALCULATION_MISSING, NUMBER_NOT_SUPPORTED | sim | sim |
| M19 | rejected | `NUMBER_NOT_SUPPORTED` | NUMBER_NOT_SUPPORTED | sim | sim |
| M20 | rejected | `OUT_OF_SCOPE_ADVICE` | OUT_OF_SCOPE_ADVICE | sim | sim |

Uma execução, gabarito público e não cego; heurísticas lexicais exigem revisão humana dos casos sinalizados.
