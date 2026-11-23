# 0016 — Arquitetura multiagente: Research, Analysis, Communication e Validation

- **Status:** Aceita (18/11/2026, issue [#61](https://github.com/moonshinerd/trokim/issues/61), com o contrato como foi implementado)
- **Data:** 16/11/2026 (proposta) · 18/11/2026 (aceita)
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

## Como foi implementado

O contrato do épico foi implementado sem mudanças de campos. O que a implementação acrescentou:

- **Communication extrativo.** O rascunho do modelo só é aceito se for composto de frases
  copiadas literalmente das evidências, cada uma com a citação `[n]` correta, e das linhas
  exatas dos cálculos do Analysis. Fora disso, o agente troca o texto por um rascunho seguro
  montado com os próprios trechos e cálculos; se o texto do modelo trouxer número sem suporte,
  registra o bloqueio `DRAFT_NOT_GROUNDED`. O prompt é `api/app/prompts/prompt_agente_comunicacao_v1.txt`.
- **Códigos do Validation:** `NUMBER_NOT_SUPPORTED`, `CITATION_INVALID`, `OUT_OF_SCOPE_ADVICE`,
  `ABSTENTION_MISMATCH`, `CALCULATION_MISSING` e `DRAFT_NOT_GROUNDED` (repassado do
  Communication). Todos são regras determinísticas, sem LLM.
- **Revisões:** `max_revisions = 1`. Persistindo o bloqueio, a resposta é `rejected` e o rascunho
  fica retido.
- **Roteamento do Analysis:** por palavras-chave (`needs_analysis` em
  `api/app/services/agents/orchestrator.py`); sem números na pergunta, o passo é `skipped`.
- **Endpoint:** `POST /v1/agents/ask` (1 a 1000 caracteres) devolve `MultiAgentResponse`; `503`
  quando o modelo está indisponível. O app mostra a trilha em "Como cheguei a essa resposta"
  (issue [#59](https://github.com/moonshinerd/trokim/issues/59)).
- **Medição:** benchmark da issue [#60](https://github.com/moonshinerd/trokim/issues/60), com os 30
  casos da Semana 3 como quarta abordagem e os 20 cenários do
  [gabarito multiagente](../pesquisa/gabarito-multiagente.md); resultados em
  [Histórico de Resultados](../pesquisa/resultados.md).

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
- A latência sobe (um passo a mais, e possivelmente uma revisão). Medido na
  [#60](https://github.com/moonshinerd/trokim/issues/60): 3,5 s por caso com o Qwen de 1,5 B e
  3,7 s com o GPT-6 Luna, contra 1,5 s e 2,6 s do Trokim estruturado; quase todo o tempo é o do
  modelo no Communication.
- A validação por regras tem falsos positivos e negativos: ela é uma camada de segurança, não
  uma prova de veracidade. As taxas medidas entram na documentação.
- O modelo de 1,5 B continua sendo o limite de qualidade da redação.
- Os agentes de pesquisa e análise trabalham sobre os lançamentos importados, que ficam na
  memória da API ([ADR 0015](0015-dados-reais-importacao-e-endereco-da-api.md)).

## Resultados medidos

Benchmark da [#60](https://github.com/moonshinerd/trokim/issues/60), com duas rodadas por modelo
(18/11 e 19/11; a de 19/11 com o protocolo corrigido do PR #85)
([Histórico de resultados, seções 8 e 9](../pesquisa/resultados.md#8-semana-4-multiagente-nos-30-casos-da-comparacao)):

- **Validation:** barrou os 5 rascunhos inválidos injetados com o código esperado em todas as
  execuções; o C30 (cálculo sem resultado do sistema) passou a ser retido com os dois modelos.
- **C29:** com o protocolo corrigido, o fluxo recebe os mesmos totais das outras abordagens e
  responde com os números do `CalculationService` (saldo de R$ 0,20) nos dois modelos.
- **Não resolvido:** o C27 (prever preço de ação) ainda é respondido, com trechos irrelevantes,
  porque a política de escopo do Research não reconhece a pergunta.
- **Redação extrativa:** o Communication só aceita frases literais das evidências e linhas exatas
  dos cálculos; na prática, quase todas as respostas foram o rascunho seguro montado com os trechos, e não
  texto do modelo (em 19/11, 26 de 28 com o GPT-6 Luna e todas as 23 com o Qwen). Isso eleva a
  cobertura de conceitos (89% contra 74% do Trokim estruturado com o Luna, 73% contra 69% com o
  Qwen), mas baixa o F1 de tokens e, com o modelo pequeno, faz o Validation reter de 6 a 9 dos 30
  casos.
- **Defeito encontrado e corrigido:** sem teto de tokens, o Qwen gerava até estourar o tempo
  limite (8 dos 30 casos, 9 dos 20 cenários). O Communication passou a usar `LLM_MAX_TOKENS`.
- **Próximo passo:** aceitar paráfrase com citação verificada, em vez de só frases literais, e
  ampliar a política de escopo para previsões de preço.


## Extensão: agente de documento (Semana 5, #88)

`AgentName.DOCUMENT` e `DocumentAgent.run(DocumentContext)` acrescentam um passo de leitura
com o mesmo `AgentStep`, sem executar o pipeline de pesquisa e comunicação do chat.
O contexto próprio exclui os bytes de serialização e representação; a operação apaga sua
referência ao arquivo ao terminar. A integração ao orquestrador HTTP pertence à #96.
O contrato público do épico #86 fica em `domain/documents.py` e deve ser compartilhado
com a #89. O agente usa diretamente as portas `OcrProvider` e `VisionProvider` da #87
(ADR 0021), com seus resultados tipados e suas fábricas configuráveis.
A leitura, os limites e as pendências estão no [Agente de documento](../agentes/document-agent.md).
