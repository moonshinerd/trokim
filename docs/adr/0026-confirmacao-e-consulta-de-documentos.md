# 0026 — Confirmação integral e consulta local de documentos

- **Status:** Aceita
- **Data:** 25/11/2026
- **Requisitos / GQs:** RF27, RF28, RF31, RNF12; GQ02, GQ03, GQ05
- **Issue:** [#96](https://github.com/moonshinerd/trokim/issues/96)
- **ADRs relacionadas:** [0016](0016-arquitetura-multiagente.md), [0018](0018-contas-periodos-transferencias-e-visoes.md), [0021](0021-visao-e-ocr-modulares.md), [0024](0024-persistencia-local-e-backup-criptografado.md)

## Contexto

Um documento pode conter uma operação ou várias compras. Validar cada linha isoladamente
perde o total necessário à conciliação de faturas. Marcar a procedência em `source_kind`
também altera o significado de caixa e competência, que usam esse campo para distinguir
compras do cartão. A consulta desses dados precisa citar a origem sem misturar interpretação
de perguntas, cálculo e redação com a coordenação geral dos agentes.

## Decisão

- A confirmação prepara os lançamentos em memória, valida o documento inteiro contra a
  biblioteca e só então aplica o lote. Um bloqueio não cria contas nem lançamentos.
- A conta informada restringe a conciliação; sem conta explícita, a procura de duplicatas
  permanece global, como na extração. Faturas sem conta vão para `documentos:cartao`;
  os demais documentos, para `documentos:sem_conta`.
- Reenvios reconhecidos pela identidade do lançamento são excluídos apenas da comparação
  de duplicatas. Datas, vencimento, campos obrigatórios, total e pagamentos já conciliados
  continuam sujeitos à validação, mesmo quando o resultado seria `repetido`.
- `Transaction.origin` distingue `importacao` de `documento`; `source_kind` conserva seu
  significado de conta ou cartão. A procedência é um campo aditivo do JSON de
  `library_snapshot`, herdado por `StoredTransaction`. Não há coluna SQL nova e, portanto,
  não é necessária uma revisão Alembic. Retratos sem o campo recebem `importacao`.
- O estabelecimento revisado alimenta as regras de categoria existentes, inclusive em Pix.
  A classificação de pessoa ou empresa reutiliza o mecanismo dos perfis bancários.
- `DocumentPipeline` coordena extração e validação. `AgentQueryService` resolve a consulta
  local do estabelecimento, usa `CalculationService` e valida o texto com `ValidationAgent`.
  A evidência é a biblioteca local; a trilha cita os identificadores e a origem confirmada.
  Esse fluxo não precisa de LLM nem pesquisa institucional para somar os próprios dados.
  Perguntas educacionais continuam no `Orchestrator` com os quatro agentes.

## Consequências

A mesma confirmação trata operações simples e lotes sem simular requisições por linha nem
manter cópias mutáveis da biblioteca. A origem sobrevive ao SQLite e ao backup sem interferir
nos cálculos existentes. Sem referência válida, a consulta local pede esclarecimento;
um bloqueio do validador retém a resposta. A seleção por conta, dono e período continua
no escopo das #94 e #95.

## Ajustes da revisão

- Compras idênticas no mesmo dia dentro de um documento recebem identificador próprio pela
  ocorrência (`:1`, `:2`...); o reenvio do mesmo documento continua reconhecido linha a linha.
  Duas confirmações separadas de um único lançamento idêntico seguem como “repetido”.
- Fatura de cartão só é lançada em conta de cartão (`ACCOUNT_KIND_MISMATCH`, 422).
- O passo de validação da trilha usa `failed` quando há bloqueio.
- Queda do cliente durante o envio responde 400, sem erro 500.
- **Abstenção e confirmação manual:** a abstenção do `/extract` não cria nada, mas o `/confirm`
  aceita os campos que o usuário revisou ou digitou, mesmo sem leitura bem-sucedida. A validação
  determinística vale do mesmo jeito.

## Ajustes da Semana 5 ([#117](https://github.com/moonshinerd/trokim/issues/117), 27/11/2026)

- **Origem manual.** O `/confirm` recebe `origin`: `documento` (padrão, o usuário revisou o que
  foi lido) ou `manual` (digitou sem leitura bem-sucedida, por exemplo depois de uma abstenção).
  `Transaction.origin` ganha o valor `manual`, e o chat descreve esse lançamento como "digitado
  por você na tela de documento, sem leitura de foto ou PDF". Exigir uma extração prévia foi
  descartado: a API é sem estado ([ADR 0025](0025-armazenamento-no-aparelho-e-api-sem-estado.md))
  e não guarda a leitura entre `/extract` e `/confirm`.
- **Extrato depois do comprovante.** A conciliação deixava de valer quando o comprovante era
  confirmado antes do extrato do mesmo Pix: os dois entravam nos totais. Agora a importação do
  OFX procura, entre os lançamentos de documento (lidos ou digitados) ainda ativos, um com o
  mesmo tipo, data, valor e favorecido (`payee_matches`, a mesma regra da validação de
  duplicatas) e o marca como duplicata: o extrato do banco prevalece. Documento lançado numa
  conta real só concilia com o extrato dessa conta. O upload informa `documents_reconciled`.
