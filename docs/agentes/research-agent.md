# Research Agent

!!! success "Status: Implementado"
    Implementado na issue [#52](https://github.com/moonshinerd/trokim/issues/52). Primeira linha de defesa defensiva do Trokim, encapsulando recuperação vetorial e lexical contra as 20 fontes oficiais regulamentadas.

O **Research Agent** (`api/app/services/agents/research.py`) atua como a primeira etapa do pipeline multiagente. Sua missão é garantir que nenhuma pergunta fora de escopo (recomendações de compra/venda de ativos, promessas de retorno, código, poemas) ou desprovida de embasamento documental chegue ao modelo gerador de linguagem ([ADR 0003](../adr/0003-rag-fontes-oficiais.md) e [ADR 0016](../adr/0016-arquitetura-multiagente.md)).

O agente é 100% determinístico e opera sem nenhum modelo generativo (LLM).

## Comportamento e Decisão

```mermaid
flowchart TD
    Q[ctx.question] --> Scope{is_outside_scope?}
    Scope -->|Sim (apostas, ações, cripto, código)| F[abstain_reason = 'fora_de_escopo'<br/>passo: ABSTAINED]
    Scope -->|Não| Ret[RAGService.retrieve_evidence]
    Ret --> EvCheck{Evidências acima do limiar?}
    EvCheck -->|Sim| OK[ctx.evidences preenchido<br/>passo: OK]
    EvCheck -->|Não| NumCheck{needs_analysis?}
    NumCheck -->|Sim| OKNum[ctx.evidences = vazio<br/>passo: OK para Análise]
    NumCheck -->|Não| SemEv[abstain_reason = 'sem_evidencia'<br/>passo: ABSTAINED]
```

| Situação | Motivo de Abstenção | Status do Passo | Comportamento no Contexto |
|---|---|:---:|---|
| Pergunta fora de escopo regulatório (apostas, cripto, código, poemas, golpes) | `fora_de_escopo` | `abstained` | Bloqueia execução imediata; encerra sem LLM. |
| Pergunta educacional/conceitual sem suporte regulatório | `sem_evidencia` | `abstained` | Bloqueia e impede que o LLM alucine regras inexistentes. |
| Pergunta estritamente orçamentária sobre extratos locais | *(nenhum)* | `ok` | `ctx.evidences` vazio; delega resolução ao Analysis Agent. |
| Evidências oficiais encontradas acima do limiar | *(nenhum)* | `ok` | Popula `ctx.evidences` com trechos, URLs e pontuações. |

## Estrutura do Passo (`AgentStep.detail`)

O passo devolvido pelo Research Agent enriquece a trilha de auditoria com metadados detalhados:

```json
{
  "top_k": 3,
  "threshold": 0.15,
  "scores": [0.8912, 0.7421],
  "documents": ["bcb_orcamento.txt", "cvm_emergencia.txt"]
}
```

## Como Funciona na Prática (Exemplos Reais)

1. **Consulta Educacional Válida:**
   - *Pergunta:* "Como montar uma reserva de emergência?"
   - *Resultado:* Passo `ok`, `ctx.evidences` com 3 trechos de `cvm_emergencia.txt` e `bcb_orcamento.txt`.
2. **Caso C28 (Armadilha de Resolução Inexistente):**
   - *Pergunta:* "Explique a Resolução 9999 inexistente do BCB sobre empréstimos obrigatórios."
   - *Resultado:* A pontuação de similaridade não atinge o limiar de 0,15. Passo `abstained` com `abstain_reason = "sem_evidencia"`. O orquestrador responde com a mensagem fixa de abstenção ética sem acionar o LLM.
3. **Pergunta Fora de Escopo:**
   - *Pergunta:* "Qual criptomoeda devo comprar para ter retorno garantido?"
   - *Resultado:* Filtro defensivo acionado. Passo `abstained` com `abstain_reason = "fora_de_escopo"`.
4. **Pergunta de Lançamentos da Sessão:**
   - *Pergunta:* "Qual o total de despesas por categoria nos lançamentos importados?"
   - *Resultado:* Reconhecida como intenção de cálculo sobre dados locais; passo `ok` com zero evidências documentais necessárias, liberando o fluxo para o Analysis Agent.

## Testes Automatizados

Testado em `api/tests/test_research_agent.py`:

- Recuperação de evidências institucionais em perguntas educacionais.
- Barreira contra perguntas fora de escopo (cripto, ações, códigos, poemas, golpes).
- Defesa contra alucinação de normas oficiais fictícias (caso C28).
- Fluxo transparente para perguntas analíticas sobre lançamentos.

## Limitações

- A base oficial atual contempla 20 documentos curados. Consultas sobre normativos recentes ou temas não cobertos resultarão em abstenção ativa ética, preservando o usuário contra desinformação financeira.
