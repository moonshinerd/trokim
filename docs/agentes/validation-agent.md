# Validation Agent

!!! success "Status: Implementado"
    Implementado na issue [#54](https://github.com/moonshinerd/trokim/issues/54). Última linha de defesa defensiva do Trokim, garantindo que nenhuma resposta seja entregue ao usuário com dados alucinados ou conselhos fora de escopo.

O **Validation Agent** (`api/app/services/agents/validation.py`) opera como o auditor independente do sistema multiagente. Ele analisa o rascunho produzido pelo Communication Agent antes de sua liberação final, avaliando aderência factual, integridade das citações e conformidade de escopo ([ADR 0016](../adr/0016-arquitetura-multiagente.md)). É 100% determinístico e não recorre a LLMs.

## Regras de Validação e Códigos de Bloqueio

| Código | Severidade | Gatilho de Bloqueio | Caso da Semana 3 |
|---|:---:|---|:---:|
| `NUMBER_NOT_SUPPORTED` | **BLOCKER** | Grandeza numérica (moeda, percentual, prazo) sem respaldo em `calculations` ou `evidences` | C29, C04, C17 |
| `CITATION_INVALID` | **BLOCKER** | Citação inválida ou ausente (aceita links clicáveis com o nome da fonte `[Nome](url)` e numeração `[n]`) | Heurística RAG |
| `OUT_OF_SCOPE_ADVICE` | **BLOCKER** | Indicação de ativo financeiro específico, promessa de rentabilidade ou previsão de preço | C27 |
| `ABSTENTION_MISMATCH` | **BLOCKER** | Texto substantivo emitido quando já existia motivo de abstenção registrado | Política ética |
| `CALCULATION_MISSING` | **BLOCKER** | Pergunta que demandava cálculo sobre lançamentos sem cálculos gerados pelo sistema | C30 |

## Extração de Números sem Falsos Positivos

Na Semana 3, a heurística de validação apresentava falsos positivos ao confundir numeração de tópicos estruturais com dados factuais. O Validation Agent resolveu isso com filtros estruturais em cascata:

1. **Marcadores de citação e links:** `[1]`, `[2]` e links Markdown `[Nome da Fonte](url)` são desconsiderados na extração de números, evitando que URLs com dígitos gerem falsos positivos.
2. **Listas ordenadas:** Numerações de início de linha ou pós-pontuação (`1. `, `2) `, `Passo 1:`) são expurgadas antes da análise factual.
3. **Identificadores legais:** Menções a normas (`Resolução 4.966`, `Lei 14.181`, `art. 5º`) são preservadas no texto mas ignoradas como grandezas monetárias.
4. **Anos de calendário:** `2024`, `2025`, `2026` não são tratados como valores de cálculo.

## Taxa de Falso Positivo Medida

Em bateria de testes automatizados com **10 rascunhos bons legítimos** em linguagem natural (cobrindo listas numeradas, metas em meses, regras 50/30/20, explicações conceituais e consultas combinadas), a taxa de falso positivo registrada foi de:

$$\text{Taxa de Falso Positivo} = 0\% \quad (0 \text{ bloqueios indevidos em } 10 \text{ casos testados})$$

## Como Funciona nos Casos de Regressão da Semana 3

- **Caso C27 (Previsão de Preço / Recomendação):**
  - *Rascunho:* "Recomendo comprar ações com preço alvo de R$ 45,00."
  - *Ação:* Bloqueado com `OUT_OF_SCOPE_ADVICE`. O orquestrador aciona revisão ou rejeita com segurança.
- **Caso C29 (Percentual Extrapolado):**
  - *Rascunho:* "Você deve destinar 33,33% para despesas fixas."
  - *Ação:* Bloqueado com `NUMBER_NOT_SUPPORTED` (33,33% não existe nas fontes oficiais nem nos cálculos).
- **Caso C30 (Cálculo sem Dado do Sistema):**
  - *Rascunho:* "Seu saldo calculado é de R$ 1.850,00." (sem nenhum lançamento processado).
  - *Ação:* Bloqueado com `CALCULATION_MISSING`.

## Testes Automatizados

Implementados em `api/tests/test_validation_agent.py`:

- Bloqueio determinístico nos cenários de regressão C27, C29, C30, C04 e C17.
- Rejeição de citações fora do intervalo de evidências recuperadas.
- Validação estrita de abstenção.
- Bateria de não-regressão em rascunhos bem-formados com zero falsos positivos.

## Limitações

- A validação baseia-se em regras léxicas e numéricas determinísticas. Paráfrases de alta complexidade sem numerais ou conselhos sutis que não usem termos explícitos podem passar como avisos, motivo pelo qual a curadoria do prompt do Communication Agent permanece complementar.
