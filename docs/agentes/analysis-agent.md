# Analysis Agent

!!! success "Status: Implementado"
    Implementado na issue [#53](https://github.com/moonshinerd/trokim/issues/53). O motor determinístico de cálculo financeiro elimina alucinações aritméticas e assegura conformidade estrita com a ADR 0004.

O **Analysis Agent** (`api/app/services/agents/analysis.py`) computa grandezas numéricas no fluxo educacional, usando `CalculationService`, sem modelos generativos (LLMs). A consulta local de um estabelecimento confirmado usa o mesmo serviço de cálculo em `AgentQueryService`, com validação independente antes da resposta.

## Intenções Suportadas e Fórmulas

| Intenção | Palavras-chave | O que calcula | Função no `CalculationService` | Unidade |
|---|---|---|---|:---:|
| **Resumo** | `saldo`, `receita`, `despesa`, `gastei`, `resumo`, `balanco`, `total`, `poupança` | Receitas totais, despesas totais, saldo líquido e taxa de poupança | `calculate_summary` | `BRL`, `%` |
| **Categorias** | `categoria`, `alimentacao`, `moradia`, `transporte`, `saude`, `lazer`, `educacao`, `servicos` | Total por categoria e participação percentual sobre as despesas totais | `category_shares` | `BRL`, `%` |
| **Meta** | `meta`, `juntar`, `meses`, `tempo`, `objetivo`, `poupando` | Prazo em meses para alcançar um objetivo: $\lceil \text{meta} / \text{aporte} \rceil$ | `months_to_goal` | `meses` |
| **Cenários** | `cenario`, `comparar`, `simulacao` | Margem operacional e delta de poupança entre propostas | `compare_budget_scenarios` | `BRL` |

## Princípio de Abstenção Numérica

Se a consulta exigir dados dos extratos e não houver lançamentos carregados na sessão da API, o agente:

1. Registra a premissa explicativa em `ctx.assumptions`: *"Nenhum lançamento foi importado para calcular o resumo financeiro."*
2. Emite o passo com status `skipped` sem chutar ou estimar grandezas.
3. Garante que o Communication Agent receba a premissa e solicite a importação do extrato (OFX/PDF) ao usuário.

## Extração de Metas em Linguagem Natural

O agente extrai valores monetários diretamente da pergunta do usuário:

- Formatos aceitos: `R$ 6.000`, `R$ 6.000,00`, `6000 reais`, `6 mil`, `500 reais por mês`.
- Exemplo: *"Em quantos meses consigo juntar R$ 6.000 poupando R$ 500 por mês?"*
  - $\text{Objetivo} = 6.000,00$ BRL
  - $\text{Aporte} = 500,00$ BRL
  - $\text{Meses} = \lceil 6000 / 500 \rceil = 12$ meses.

## Exemplo de Saída (`CalculationResult`)

```json
[
  {
    "key": "net_balance",
    "label": "Saldo líquido",
    "value": 2500.0,
    "unit": "BRL",
    "source": "CalculationService.calculate_summary"
  },
  {
    "key": "savings_rate",
    "label": "Taxa de poupança",
    "value": 50.0,
    "unit": "%",
    "source": "CalculationService.calculate_summary"
  },
  {
    "key": "months_to_goal",
    "label": "Meses necessários",
    "value": 12,
    "unit": "meses",
    "source": "CalculationService.months_to_goal"
  }
]
```

## Testes Automatizados

O comportamento do Analysis Agent e as rotinas matemáticas são cobertos em:

- `api/tests/test_calculations.py`: funções puras `months_to_goal`, `category_shares`, `calculate_summary` e `compare_budget_scenarios`.
- `api/tests/test_analysis_agent.py`: extração de metas em pt-BR, cálculo consolidado de categorias e comportamento defensivo com lista de transações vazia.

## Limitações

- O cálculo de meta atual assume aporte fixo e linear sem juros compostos ou inflação. Essa premissa é explicitada nas `assumptions` entregues ao Communication Agent.

## Documentos confirmados

“Quanto gastei nessa loja?” recebe `document_uid`; também é aceito o nome exato do
estabelecimento, sem distinção de acentos, espaços repetidos ou maiúsculas.
`AgentQueryService` considera só despesas de documentos confirmados (o total, a citação e a
origem falam dos mesmos lançamentos), exclui duplicatas e transferências próprias, soma pelo
`CalculationService` e produz passos `analysis` e `validation`. A resposta cita a
biblioteca local e a origem “lido de foto ou PDF, confirmado por você”, sem enviar os
lançamentos ao LLM. Em “nessa loja” sem documento identificado, pede esclarecimento. Perguntas
por nome que não casam com nenhum estabelecimento de documento (por exemplo, “quanto gastei em
janeiro?”) seguem para o orquestrador.
Veja os [exemplos completos](document-agent.md#consulta-do-lancamento-confirmado).
