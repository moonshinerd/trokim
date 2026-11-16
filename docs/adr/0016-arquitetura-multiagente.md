# 0016 — Arquitetura multiagente: Research, Analysis, Communication e Validation

- **Status:** Proposta (vira "Aceita" na issue [#61](https://github.com/moonshinerd/trokim/issues/61), com o contrato como foi implementado)
- **Data:** 16/11/2026
- **Requisitos / GQs:** RF18, RF19, RF20, RF21; GQ01, GQ05, GQ10, GQ11
- **Issues:** [#50](https://github.com/moonshinerd/trokim/issues/50) (épico), [#51](https://github.com/moonshinerd/trokim/issues/51) a [#61](https://github.com/moonshinerd/trokim/issues/61)
- **ADRs relacionadas:** [0003](0003-rag-fontes-oficiais.md), [0004](0004-calculos-deterministicos.md), [0008](0008-material-comparativo-versionado.md), [0009](0009-sintese-generativa-local.md)

## Contexto

Na Semana 3 o Trokim estruturado errou nos casos C27 (respondeu o que devia recusar), C29
(extrapolou percentuais) e C30 (calculou sem o resultado do sistema), e a política de abstenção
acertou 1 de 3 casos esperados ([Histórico de Resultados](../pesquisa/resultados.md)). A causa
comum é que o mesmo passo recupera, calcula, escreve e se auto-avalia. O entregável oficial da
Semana 4 é o primeiro sistema multiagente.

## Decisão

Quatro agentes com papéis separados, coordenados por um orquestrador determinístico:

| Agente | Papel | Usa LLM? |
|---|---|:---:|
| [Research](../agentes/research-agent.md) | Recupera evidências oficiais e decide escopo e abstenção | Não |
| [Analysis](../agentes/analysis-agent.md) | Faz todo cálculo por código (`CalculationService`) | Não |
| [Communication](../agentes/communication-agent.md) | Redige a resposta em pt-BR só a partir de evidências e cálculos | **Sim** |
| [Validation](../agentes/validation-agent.md) | Confere o rascunho: números sem suporte, citações, escopo e abstenção | Não |

O [orquestrador](../agentes/orquestrador.md) segue as regras: (1) Research; se houver motivo de
abstenção, encerra sem chamar o LLM; (2) Analysis só se a pergunta pede números; (3)
Communication escreve o rascunho; (4) Validation confere, com **uma** revisão do Communication
em caso de bloqueio e, persistindo o bloqueio, **rejeição segura** sem inventar conteúdo; (5) cada
passo vira uma linha da **trilha** (`AgentStep`) devolvida com a resposta.

**Contrato.** Os modelos (`AgentContext`, `AgentStep`, `CalculationResult`, `ValidationIssue`,
`MultiAgentResponse`) ficam em `api/app/domain/agents.py` (domínio puro) e o protocolo `Agent`
em `api/app/services/agents/base.py`. O contrato completo está no épico [#50](https://github.com/moonshinerd/trokim/issues/50) e na página
[Agentes](../agentes/index.md). O endpoint é `POST /v1/agents/ask`; `/v1/chat/ask` e
`/v1/chat/generate` continuam existindo.

## Alternativas consideradas

- **Um único agente com ferramentas (tool calling):** mantém o problema de o modelo decidir
  sozinho quando calcular e quando se abster, e não dá uma checagem independente.
- **Framework de agentes (LangGraph e similares):** adiciona dependência e comportamento
  não determinístico para um fluxo que cabe em um orquestrador de poucas regras; fica como
  opção para a Semana 5, se a multimodalidade exigir.
- **Validation com LLM como juiz:** reintroduziria a variação entre execuções observada na
  Semana 3; a validação determinística é auditável e reproduzível.

## Consequências

- O cálculo e a validação continuam testáveis sem modelo, e o CI segue determinístico.
- A latência sobe (um passo a mais, e possivelmente uma revisão); isso é medido na issue [#60](https://github.com/moonshinerd/trokim/issues/60).
- A validação por regras tem falsos positivos e negativos: ela é uma camada de segurança, não
  uma prova de veracidade. As taxas medidas entram na documentação.
- O modelo de 1,5 B continua sendo o limite de qualidade da redação.
- Os agentes de pesquisa e análise trabalham sobre os lançamentos importados, que ficam na
  memória da API ([ADR 0015](0015-dados-reais-importacao-e-endereco-da-api.md)).
