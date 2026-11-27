# Orquestrador e Contratos

!!! success "Status: Implementado"
    Implementado na issue [#51](https://github.com/moonshinerd/trokim/issues/51). O contrato de mensagens é estrito e a orquestração segue um fluxo linear defensivo com revisão única em caso de bloqueio.

Coordena os quatro agentes especializados dos fluxos educacional e pessoal e constrói a trilha de auditoria (`steps`). O código está estruturado em:

- `api/app/domain/agents.py`: contratos tipados, incluindo `FinancialIntent` e `FinancialContext`, sem acesso à infraestrutura. O contexto financeiro exige intenção e data de referência e fica excluído da serialização do contexto geral.
- `api/app/services/agents/base.py`: protocolo assíncrono `Agent`.
- `api/app/services/agents/orchestrator.py`: classe `Orchestrator` e função de roteamento `needs_analysis`.

## Regras de Execução

Consultas pessoais identificadas pelas regras da RF30 marcam Research como `skipped`: os
arquivos importados são a fonte factual. Quando a pergunta também pede orientação, Research
continua obrigatório, com a política institucional de escopo e abstenção. O RAG só é inicializado
quando utilizado. Analysis recebe uma cópia dos lançamentos, contas e faturas para manter a
consulta consistente durante as chamadas assíncronas. Quando a biblioteca é fornecida, ela é
a fonte única dos lançamentos; o parâmetro antigo `transactions` atende chamadas sem biblioteca. Chamadas internas ao contrato anterior,
com apenas uma lista de lançamentos, preservam o fluxo educativo; a RF30 é ativada ao fornecer
a biblioteca, como faz o endpoint da API. Dados ausentes ou ambiguidades produzem
esclarecimento validado, com Communication `skipped` e sem LLM.

As regras numeradas abaixo descrevem o fluxo educacional. Antes dele, `AgentQueryService` resolve as
consultas locais de estabelecimentos identificados em documentos confirmados. Esse fluxo
tem cálculo determinístico e validação independente, sem pesquisa institucional nem LLM;
veja a [ADR 0026](../adr/0026-confirmacao-e-consulta-de-documentos.md).

1. **Research Agent (Primeira Linha de Defesa):** Recupera evidências institucionais. Se `abstain_reason` for preenchido (fora de escopo ou sem evidência suficiente), o orquestrador encerra a execução com status `abstained` e devolve a mensagem fixa de abstenção imediatamente, sem acionar o LLM.
2. **Analysis Agent (Cálculo Determinístico):** É executado somente se a pergunta demandar números ou raciocínio orçamentário sobre extratos (`needs_analysis`). Caso contrário, o passo é marcado como `skipped`.
3. **Communication Agent (Redação em pt-BR):** Elabora o rascunho de resposta (`draft_answer`) ancorando-se estritamente nas evidências numeradas e nos cálculos realizados.
4. **Validation Agent (Guarda Defensivo):** Audita o rascunho. Caso encontre problemas com severidade `blocker` e ainda haja tentativas disponíveis (`max_revisions = 1`), o orquestrador reenvia o contexto para revisão do Communication Agent. Caso o bloqueio persista ou se esgotem as revisões, encerra com status `rejected` e uma mensagem fixa de segurança, sem inventar conteúdo.
5. **Trilha de Auditoria e Resiliência:** Cada etapa registra um `AgentStep` com status, duração em milissegundos e sumário. Qualquer falha inesperada em um agente é capturada de forma defensiva, convertida em `failed` na trilha e resulta em `rejected` seguro para o usuário final.

## Regras de Detecção Numérica (`needs_analysis`)

Para o fluxo educativo, a função `needs_analysis(question)` normaliza acentuações e avalia a presença de palavras-chave orçamentárias:

- Saldo, receitas, despesas, gastei, gasto, gastos.
- Categoria, categorias, poupança, poupar, meta, metas, meses.
- Cenário, cenários, projeção, projeções, quanto, orçamento, guardar, economizar.

Perguntas conceituais puras (ex.: *"O que é o FGC?"* ou *"Explique a regra 50/30/20"*) pulam a etapa de análise com status `skipped`.

## Filtros do endpoint

`POST /v1/agents/ask` mantém `message` (obrigatório, de 1 a 1000 caracteres) e `document_uid`
(opcional), acrescentando os seguintes campos opcionais no mesmo objeto JSON:

| Campo | Formato | Regra |
|---|---|---|
| `account_id` | string do `GET /v1/accounts` | Conta precisa existir; o id não vai ao modelo |
| `owner` | `pessoal`, `empresa`, `todas` | Recorte por dono; conflito com o texto pede esclarecimento |
| `period` | `AAAA-MM`, expressão de mês/intervalo ou `fatura_aberta`, `fatura_fechada`, `proxima_fatura` | Período inválido ou contraditório pede esclarecimento |

Sem filtro, conta e período são resolvidos pelo texto da #94. Não há memória conversacional para
resolver referências como “essa conta” em mensagens posteriores: envie os filtros novamente.
A seleção visual dos filtros no app pertence à #97. Para comparar, informe os dois períodos no
texto e deixe `period` ausente. Parcelas e dívidas representam a posição dos arquivos; não aceitam
um mês histórico como se fosse um retrato completo da dívida naquela data.

```bash
curl -X POST http://127.0.0.1:8000/v1/agents/ask \
  -H 'Content-Type: application/json' \
  -d '{"message":"Quanto gastei?","owner":"empresa","period":"2026-10"}'
```

A consulta de documento confirmado da #96 preserva o fluxo local e aplica os filtros de conta,
dono e datas quando enviados. Referência de fatura no filtro de documento pede mês ou intervalo.

## Mensagens Fixas do Sistema

- **Abstenção educativa (`ABSTAINED`):**
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

- O roteamento é por regras em pt-BR. Expressões não reconhecidas podem exigir reformular a
  pergunta. Próxima fatura e término das parcelas preservam as estimativas da camada da #94.

- O orquestrador atual segue um grafo linear determinístico com no máximo 1 ciclo de revisão. Não há suporte a branching complexo ou chamadas paralelas, o que é intencional para manter rastreabilidade estrita e latência previsível.

### Organização da política financeira

A classificação não depende do estado da biblioteca. A resolução produz uma `ChatSelection`
compartilhada com a consulta de documentos; a execução valida os períodos permitidos para cada
intenção antes de chamar seu executor. As respostas com contexto completo são montadas em um
único lugar, preservando os retornos de abstenção sem contexto. Uma alteração na biblioteca
durante a pesquisa não muda os números da consulta já iniciada.
