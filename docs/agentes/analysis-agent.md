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

## Consultas sobre os seus dados

Além do resumo global, a camada `FinancialQueryService`
(`api/app/services/financial_query_service.py`, [RF30](../requisitos.md)) calcula, sem LLM, o que o
chat precisa para responder sobre a vida financeira do usuário. Todas as funções são puras sobre a
biblioteca local, reaproveitam o `CalculationService` (transferência própria e pagamento de fatura
ficam fora dos totais, [ADR 0018](../adr/0018-contas-periodos-transferencias-e-visoes.md)) e somam em
`Decimal`. Cada uma devolve `CalculationResult` (chave, rótulo, valor, unidade e `source`).

| Pergunta de exemplo | Função | O que devolve |
|---|---|---|
| “Quanto gastei em cada conta em outubro?” | `by_account` | Gasto, receita e saldo por conta |
| “E nas contas da empresa?” | `by_owner` | Gasto, receita e saldo do dono (`pessoal` ou `empresa`) |
| “Quanto está a fatura aberta?” | `statement_total("aberta")` | Total da fatura e a data de fechamento |
| “Quanto foi a fatura fechada?” | `statement_total("fechada")` | Total da última fatura fechada do cartão |
| “Como será a próxima fatura?” | `next_statement` | Parcelas já contratadas do próximo ciclo (estimativa) |
| “Quanto falta nas parcelas?” | `open_installments` | Quanto falta, valor mensal e quando termina |
| “O que eu devo?” | `commitments` | Parcelas futuras, fatura fechada a pagar e estimativa dos próximos 30 dias |
| “Onde mais gastei em setembro?” | `top_merchants`, `top_categories` | Ranking do período |
| “Gastei mais em outubro ou em novembro?” | `compare_periods` | Gasto nos dois períodos, diferença e variação percentual |
| “Quanto saiu só por transferência?” | `own_transfers_effect` | O que ficou fora dos totais |

**Período e conta a partir do texto.** `resolve_period`, `resolve_periods` e `resolve_scope`
entendem “mês passado”, “este mês”, nome do mês (com ou sem ano), “últimos 30 dias”, “de 01/10 a
15/10”, “fatura aberta, fechada e próxima” e “empresa”, “pessoal” ou “fatura do Nubank”. Mês sem
ano tem como candidatos o último que já passou e os anos com lançamentos naquele mês; se houver
mais de um, a função pergunta de qual ano. **Se há ambiguidade**
(“fatura do Nubank” com um cartão pessoal e um da empresa, ou um mês presente em dois anos), a
função devolve uma `Clarification` com a pergunta e as opções, e **nenhum número**.

**Privacidade.** O que sai é agregado, rótulo de conta (banco, tipo e dono, como “Nubank cartão
(empresa)”) e estabelecimento. Nunca documento, agência, número da conta ou nome de pessoa física.

**O que é exato e o que não é.** Cada número diz a base que o sustenta, sem chute:

- *Parcelas que faltam*, *fatura aberta* e *fatura fechada*: exatos, calculados sobre o que foi
  importado.
- *Fatura fechada a pagar*: total da última fatura fechada de cada cartão menos os pagamentos de
  fatura lançados no cartão depois do fechamento. Nos PDFs de cartão, que não trazem o pagamento, um débito de pagamento de fatura na conta
  corrente do mesmo dono, de exatamente o valor devido e depois do corte, quita a fatura. Não
  distingue qual fatura cada pagamento quitou. Com duas faturas fechadas pagas no mesmo mês, o
  valor pode sair errado: ligar cada pagamento à sua fatura é uma melhoria futura.
- *Vence nos próximos N dias*: soma só a fatura fechada a pagar cujo **vencimento está informado**
  no arquivo (`Statement.due_date`, lido dos PDFs do Itaú e do PicPay). O OFX não traz o
  vencimento; a parte sem data sai separada em `closed_due_without_date` e **não** entra na
  janela. A fatura fechada cujo vencimento informado já passou sai em `overdue_statement_due`, de
  modo que vencida, na janela e sem data somam o que há a pagar (nos PDFs do Itaú e do PicPay, o
  corte dos pagamentos é a última compra da fatura, porque o fim do período é o vencimento). As parcelas previstas na janela saem em `installments_in_window`, também à parte.
- *Próxima fatura*: as parcelas já contratadas cuja data cai no próximo ciclo (começa no dia
  seguinte ao fechamento da fatura aberta e dura um mês). Compras novas ainda não existem e não
  entram. O valor é exato para o que já foi contratado, mas a data de cada parcela é estimada
  pelo mês (data da última parcela vista mais k meses), então uma compra perto da virada do ciclo
  pode cair no ciclo vizinho.

**Recortes que não existem ou não têm datas.** Se o texto cita um banco que não foi importado
(“parcelas do Mercado Pago”), o recorte vem vazio e a consulta responde que nenhuma conta combina,
em vez de somar todas as contas. Um período de fatura (“top estabelecimentos da fatura aberta”)
não tem datas: as consultas por período o recusam e apontam `statement_total` e `next_statement`.

Contas ainda sem dono (pessoal ou empresa) ficam de fora dos totais por dono, e a consulta avisa
quantas. A palavra “conta” sozinha (“conta de luz”) não restringe a conta corrente; só “conta
corrente”, “conta do/da” e “extrato” restringem.

Reimportar o PDF de uma fatura já importada grava o vencimento que faltava. As chaves por conta
(`account_<hash>_*`) usam um hash curto do id da conta: estáveis e sem expor o número da conta.

Ligar essas funções ao chat é a issue [#95](https://github.com/moonshinerd/trokim/issues/95).

## Testes Automatizados

O comportamento do Analysis Agent e as rotinas matemáticas são cobertos em:

- `api/tests/test_calculations.py`: funções puras `months_to_goal`, `category_shares`, `calculate_summary` e `compare_budget_scenarios`.
- `api/tests/test_financial_queries.py`: cada consulta com valor esperado conferido à mão em `Decimal`, sobre um cenário de quatro contas (estorno, parcela, transferência própria, pagamento de fatura, vencimento informado e não informado, e período sem lançamento) e sobre o extrato sintético de três meses do gabarito multiagente; inclui ambiguidade e privacidade.
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
