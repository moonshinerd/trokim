# Orquestrador e Contratos

!!! success "Status: Implementado"
    Implementado na issue [#51](https://github.com/moonshinerd/trokim/issues/51). O contrato de mensagens é estrito e a orquestração segue um fluxo linear defensivo com revisão única em caso de bloqueio.

Coordena os quatro agentes especializados e constrói a trilha de auditoria (`steps`). O código está estruturado em:

- `api/app/domain/agents.py`: contrato puro de domínio (Pydantic v2), sem dependências de frameworks externos ou rede.
- `api/app/services/agents/base.py`: protocolo assíncrono `Agent`.
- `api/app/services/agents/orchestrator.py`: classe `Orchestrator` e função de roteamento `needs_analysis`.

## Regras de Execução

1. **Research Agent (Primeira Linha de Defesa):** Recupera evidências institucionais. Se `abstain_reason` for preenchido (fora de escopo ou sem evidência suficiente), o orquestrador encerra a execução com status `abstained` e devolve a mensagem fixa de abstenção imediatamente, sem acionar o LLM.
2. **Analysis Agent (Cálculo Determinístico):** É executado somente se a pergunta demandar números ou raciocínio orçamentário sobre extratos (`needs_analysis`). Caso contrário, o passo é marcado como `skipped`.
3. **Communication Agent (Redação em pt-BR):** Elabora o rascunho de resposta (`draft_answer`) ancorando-se estritamente nas evidências numeradas e nos cálculos realizados.
4. **Validation Agent (Guarda Defensivo):** Audita o rascunho. Caso encontre problemas com severidade `blocker` e ainda haja tentativas disponíveis (`max_revisions = 1`), o orquestrador reenvia o contexto para revisão do Communication Agent. Caso o bloqueio persista ou se esgotem as revisões, encerra com status `rejected` e uma mensagem fixa de segurança, sem inventar conteúdo.
5. **Trilha de Auditoria e Resiliência:** Cada etapa registra um `AgentStep` com status, duração em milissegundos e sumário. Qualquer falha inesperada em um agente é capturada de forma defensiva, convertida em `failed` na trilha e resulta em `rejected` seguro para o usuário final.

## Regras de Detecção Numérica (`needs_analysis`)

A função `needs_analysis(question)` normaliza acentuações e avalia a presença de palavras-chave orçamentárias:

- Saldo, receitas, despesas, gastei, gasto, gastos.
- Categoria, categorias, poupança, poupar, meta, metas, meses.
- Cenário, cenários, projeção, projeções, quanto, orçamento, guardar, economizar.

Perguntas conceituais puras (ex.: *"O que é o FGC?"* ou *"Explique a regra 50/30/20"*) pulam a etapa de análise com status `skipped`.

## Mensagens Fixas do Sistema

- **Abstenção (`ABSTAINED`):**
  > *"O Trokim não possui evidências suficientes nas diretrizes oficiais (Banco Central do Brasil, CVM, CFPB ou ANPD) para responder a essa consulta com segurança. Para sua proteção financeira, recomendamos consultar canais oficiais regulamentados."*
- **Rejeição Segura (`REJECTED`):**
  > *"A resposta preliminar gerada pelo assistente não passou pelas regras de validação e segurança do Trokim (conformidade com cálculos auditáveis e diretrizes oficiais). Por segurança financeira, a resposta foi retida."*

## Exemplo de Trilha de Auditoria (`AgentStep`)

```json
[
  {
    "agent": "research",
    "status": "ok",
    "summary": "Recuperação concluída",
    "duration_ms": 12,
    "detail": { "count": 2 }
  },
  {
    "agent": "analysis",
    "status": "ok",
    "summary": "Cálculo determinístico finalizado",
    "duration_ms": 8,
    "detail": { "calculations_count": 1 }
  },
  {
    "agent": "communication",
    "status": "ok",
    "summary": "Rascunho elaborado em pt-BR",
    "duration_ms": 420,
    "detail": { "attempt": 1, "model": "ollama/qwen2.5:1.5b" }
  },
  {
    "agent": "validation",
    "status": "ok",
    "summary": "Validação concluída sem bloqueios",
    "duration_ms": 14,
    "detail": { "issues_count": 0 }
  }
]
```

## Testes Automatizados

O comportamento do orquestrador é coberto sem dependência de modelo de IA nem rede externa em `api/tests/test_orchestrator.py`:

- Detecção de intenção numérica em `needs_analysis` (perguntas numéricas vs. conceituais).
- Curto-circuito de abstenção no Research (não aciona Communication nem Analysis).
- Passo `skipped` no Analysis quando a pergunta não pede cálculos.
- Ativação do Analysis e propagação de cálculos no contexto.
- Ciclo de revisão: blocker na 1ª validação e aprovação na 2ª validação.
- Bloqueio persistente convertendo resposta em `rejected` com mensagem segura.
- Captura resiliente de exceção em agente (passo `failed` e resposta `rejected`).

## Limitações

- O orquestrador atual segue um grafo linear determinístico com no máximo 1 ciclo de revisão. Não há suporte a branching complexo ou chamadas paralelas, o que é intencional para manter rastreabilidade estrita e latência previsível.
