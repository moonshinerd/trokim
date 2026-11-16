# Communication Agent

# Communication Agent

!!! success "Status: Implementado e integrado"
    Implementado em `api/app/services/agents/communication.py` com o prompt versionado `api/app/prompts/prompt_agente_comunicacao_v1.txt`. A suíte de testes de unidade e integração cobre redação fundamentada, ciclo de revisão, tratamento de indisponibilidade e injeção contextual.

Escreve, em português do Brasil e em tom pedagógico empático, a resposta final **somente a partir** das evidências oficiais e dos cálculos auditáveis recebidos. É o **único agente do sistema que utiliza LLM** (através da porta abstrata `LLMProvider`, [ADR 0009](../adr/0009-sintese-generativa-local.md)), garantindo que todo o restante da cadeia opere de forma 100% determinística.

## Regras do prompt (`prompt_agente_comunicacao_v1.txt`)

1. **Uso Exclusivo de Evidências:** Utiliza estritamente os trechos de documentos oficiais fornecidos pelo `ResearchAgent` para fundamentar conceitos, prazos ou regras regulatórias.
2. **Citações com Nome da Fonte Clicável:** Cita as fontes institucionais em texto legível e clicável com o nome da instituição ou documento acompanhado do link oficial (exemplo: `[Banco Central do Brasil](url)` ou `[CVM](url)`), em substituição a números opacos de índice.
3. **Cálculos Determinísticos:** Utiliza estritamente os números fornecidos pelo `AnalysisAgent` (ou pela própria pergunta do usuário). Nunca realiza somatórios, médias ou estimativas matemáticas por conta própria.
4. **Premissas e Dados Faltantes:** Se a consulta exigir informações ausentes nos lançamentos, declara abertamente a limitação com base nas premissas (`assumptions`) computadas pelo sistema.
5. **Isenção e Educação:** Não recomenda produtos específicos, apostas ou promessas de rendimento financeiro.

## Ciclo de Revisão Defensiva

Quando o `ValidationAgent` rejeita o primeiro rascunho com problemas impeditivos (`IssueSeverity.BLOCKER`, como citações ausentes ou números não suportados), o orquestrador aciona o `CommunicationAgent` em uma nova tentativa (`ctx.attempt > 0`).

O prompt injeta a seção de **Revisão Obrigatória**:

```text
ATENÇÃO - REVISÃO OBRIGATÓRIA DA TENTATIVA ANTERIOR:
A resposta anterior foi rejeitada pela validação com os seguintes problemas:
- [NUMBER_NOT_SUPPORTED / blocker] O número 'R$ 888.777,55' não possui suporte nos cálculos nem nas evidências oficiais.
Reescreva a resposta corrigindo integralmente todos os desvios acima.
```

O modelo reescreve a resposta eliminando os desvios apontados antes de uma nova checagem.

## Tratamento de Indisponibilidade

Se o serviço de inferência local (ex.: Ollama) estiver desligado ou sobrecarregado, o `CommunicationAgent` captura a exceção de rede e marca o passo como `StepStatus.FAILED`. O endpoint `/v1/agents/ask` traduz essa falha em código HTTP `503 Service Unavailable` com mensagem amigável para o usuário.

## Limitações de Modelos Compactos (1.5B)

Modelos compactos locais (como `qwen2.5:1.5b`) executam com extrema eficiência em CPU em aparelhos locais, mas exigem:
- Temperatura baixa ($\le 0,1$) para manter a fidelidade e evitar extrapolações.
- Estruturação estrita no prompt (seções claras de evidências, cálculos e premissas).
- A barreira determinística do `ValidationAgent` como salvaguarda inegociável para garantir que nenhum número inventado chegue ao usuário.
