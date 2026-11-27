# 0023 — Contexto do usuário no chat

- **Status:** Aceita
- **Data:** 25/11/2026
- **Requisitos / GQs:** RF18, RF19, RF20, RF30; GQ05, GQ07, GQ09
- **Issue:** [#95](https://github.com/moonshinerd/trokim/issues/95)
- **ADRs relacionadas:** [0004](0004-calculos-deterministicos.md), [0016](0016-arquitetura-multiagente.md), [0018](0018-contas-periodos-transferencias-e-visoes.md)

## Contexto

O chat precisa consultar contas, donos, faturas e parcelas sem delegar a matemática ou o acesso
à biblioteca ao modelo. Falta de material educativo não deve impedir uma consulta factual aos
arquivos importados. Dados financeiros continuam sujeitos às limitações dos próprios arquivos.

## Decisão

- O endpoint aceita filtros opcionais de conta, dono e período. A resolução por código reutiliza
  a #94 e pede esclarecimento quando filtros e texto divergem. Datas relativas usam São Paulo.
- Analysis consulta uma cópia dos lançamentos, contas e faturas da sessão. A biblioteca não é
  serializada para o LLM. Não há novas tabelas nem armazenamento do contexto no servidor.
- Ao modelo só chegam cálculos agregados, categorias, estabelecimentos, rótulos seguros de conta
  (banco, tipo e dono) e limitações. A pergunta original de consultas pessoais é substituída por
  uma descrição da intenção. Não são enviados arquivos, lançamentos individuais, ids de conta,
  agência, CPF, nomes de pessoas físicas ou descrições cruas. Pix de pessoa física permanece
  agregado como “Pix para pessoas”. A regra vale para modelo local e remoto.
- Consultas factuais pulam Research. Perguntas de orientação continuam sujeitas ao RAG e à
  abstenção institucional. Dados ausentes ou ambiguidades são respondidos sem LLM.
- Números pessoais exigem cálculo compatível com sinal e unidade; pergunta e RAG não autorizam
  valores. Metadados de datas e limitações são preservados literalmente. O rascunho seguro inclui
  as linhas exatas dos cálculos. O texto original do modelo também é auditado antes do fallback.
- A consulta local de documentos da #96 continua sem LLM, com origem e validação independente.

## Consequências e limites

O uso de regras e resultados tipados evita novas chamadas de modelo para interpretar a pergunta.
O RAG é inicializado apenas se necessário. A cópia local tem custo proporcional ao contexto da
sessão; o prompt cresce com os agregados, não com a lista de lançamentos.

Agregados ainda são dados financeiros: configurar um provedor remoto envia esses agregados ao
serviço escolhido. O fallback extrativo é conservador e pode produzir redação menos natural.
Pagamentos não identificam inequivocamente qual fatura foi quitada e datas de parcelas são
estimadas pelo mês. Nenhum resultado é apresentado como posição bancária confirmada.
A interface de contexto e o benchmark ampliado permanecem nas #97 e #98.

## Verificação

Os testes da API usam somente dados sintéticos e `MockLLMProvider`, verificando valores, trilha,
filtros, ambiguidade, ausência de dados, números indevidos, privacidade do prompt e regressões.
Os testes de cálculo da #94 e dos documentos da #96 permanecem ativos. Esta mudança não registra
uma nova rodada de benchmark nem substitui a homologação em aparelho real.

## Refinamento da revisão de qualidade

`FinancialContext` agrupa intenção tipada, filtros, contas, faturas e data de referência,
evita combinações de campos opcionais incoerentes e é excluído da serialização do contexto.
A biblioteca fornecida ao orquestrador é a fonte única do snapshot dos lançamentos.
Classificação, resolução e execução têm responsabilidades distintas; o mapa de executores
substitui a cadeia central de condições. A seleção é reutilizada pelo fluxo de documentos.

O suporte numérico fica em uma política compartilhada, sem importar um agente no outro.
Metadados são identificados por seus trechos literais, sem remoção destrutiva de substrings.
Moedas, sinais e unidades precisam concordar com os cálculos, inclusive no rascunho original.
A revisão acrescenta regressões para colisões de nomes de estabelecimentos, alvos parcialmente
reconhecidos, rótulo da conta selecionada e mudanças da biblioteca durante uma consulta.
