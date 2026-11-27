# Gabarito do chat com os dados do usuário (Semana 5)

Conjunto isolado da [#98](https://github.com/moonshinerd/trokim/issues/98) para medir a hipótese 4
do épico da Semana 5: o chat responde **corretamente os números das contas, parcelas e dívidas**,
sem número inventado. Ele não altera o [gabarito multiagente](gabarito-multiagente.md) da Semana 4
nem o [gabarito multimodal](gabarito-multimodal.md). Rastreabilidade: RF30; GQ04, GQ05;
[ADR 0008](../adr/0008-material-comparativo-versionado.md),
[ADR 0023](../adr/0023-contexto-do-usuario-no-chat.md).

## Composição

| Arquivo | Papel |
|---|---|
| `research/synthetic_data/generate_chat_dados.py` | Gera o extrato sintético (semente fixa `981127`) |
| `research/synthetic_data/ledger_chat_dados.json` | Três meses (setembro a novembro de 2026), 30 lançamentos |
| `research/rag_benchmark/questions_chat_dados.json` | As 20 perguntas, com filtros e gabarito |
| `research/rag_benchmark/questions_chat_dados.schema.json` | JSON Schema das perguntas |
| `research/rag_benchmark/chat_dados_manifest.json` | Hashes de todos os insumos e do runner |
| `research/rag_benchmark/chat_dados.py` | Valida schema, manifesto e gabarito |
| `research/rag_benchmark/run_chat_dados.py` | Executa e registra (`make chat-dados-run`) |

O extrato tem três contas: conta pessoal (`sintetica-pf`, Nubank), conta da empresa
(`sintetica-pj`, Banco do Brasil) e cartão pessoal (`sintetica-card`, Nubank) com fatura aberta,
fatura fechada e compras parceladas. Nenhum dado é real.

## As 20 perguntas

| Grupo | Casos | O que se espera |
|---|---|---|
| Conta e período por filtro | C01, C02, C14 | Gasto, receita e saldo da conta no mês |
| Dono (pessoal ou empresa) | C03, C04 | Os mesmos totais, somando só as contas daquele dono |
| Período no texto, sem filtro | C05 a C07 | Totais do mês citado |
| Cartão | C08 a C11 | Fatura aberta, fatura fechada, parcelas a pagar e dívida da fatura fechada |
| Comparação | C12, C13 | Gasto dos dois meses comparados |
| Pedido de esclarecimento | C15, C16, C20 | Sem número: o chat pergunta (período ambíguo ou conflito entre filtro e texto) |
| Dado ausente | C17 a C19 | Sem número: o chat diz o que falta importar |

O gabarito numérico **não é digitado à mão**: `chat_dados.py --write` o recalcula com o
`FinancialQueryService`/`CalculationService` sobre o extrato sintético, e o teste
`research/test_chat_dados.py` confere que o arquivo versionado bate com esse cálculo.

## Métricas

Cada pergunta passa pelo mesmo caminho do `POST /v1/agents/ask` (`AgentQueryService` com os
quatro agentes), sem HTTP. O runner guarda a resposta final, cada resposta crua do modelo e o
rascunho que chegou ao Validation.

| Métrica | Definição |
|---|---|
| Cálculo certo | Valor esperado presente em `calculations`, com a unidade certa (parte determinística) |
| Número entregue | O valor aparece na resposta final e a resposta foi entregue (`answered`) |
| Número inventado na resposta final | Número da resposta final sem cálculo compatível (meta 0) |
| Números inventados pelo modelo | O mesmo teste aplicado à resposta crua do modelo, antes da proteção |
| Retida pelo Validation | Resposta com status `rejected` |
| Esclarecimento ou ausência correta | Status `abstained`, sem cálculo e sem chamar o modelo |
| Falha técnica | Chamada ao modelo que falhou ou passo que não seja a validação com status `failed` |

A rejeição pelo Validation **não** é falha técnica: é a decisão de segurança da
[ADR 0023](../adr/0023-contexto-do-usuario-no-chat.md), que audita também o texto original do
modelo e retém a resposta quando ele inventa número, mesmo que o rascunho seguro esteja correto.

## Como reproduzir

```bash
cd api && uv run python ../research/rag_benchmark/chat_dados.py         # valida
make chat-dados-run RUN=2026-11-27-chat-dados-qwen2.5-1.5b-v2 MODEL=ollama/qwen2.5:1.5b
```

O runner recusa um `RUN` já existente. Os resultados ficam em
`research/rag_benchmark/results/chat_dados/<RUN>/` (`run.json` e `readings.json`) e estão no
[Histórico de resultados](resultados.md#11-semana-5-motores-de-leitura-e-chat-com-os-dados-do-usuario).

## Limites

Sem revisão humana cega. Um extrato de três meses e 20 perguntas não cobrem a variedade de
bancos e de formulações reais. Os filtros são enviados como o app os envia; perguntas com
linguagem muito diferente das regras de intenção da #95 não estão representadas.
