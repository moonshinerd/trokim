# 0015 — Resumo e extratos com dados reais da API, importação pelo app e endereço da API editável

- **Status:** Aceita
- **Data:** 16/11/2026
- **Requisitos / GQs:** RF01, RF02, RF07, RF15, RNF03, RNF10; GQ01, GQ02, GQ03, GQ07
- **Issue:** #45
- **ADRs relacionadas:** [0004](0004-calculos-deterministicos.md), [0005](0005-importacao-local-ofx-pdf.md), [0013](0013-preferencias-locais-e-aba-de-ajustes.md)

## Contexto

Depois do redesenho (#43), as telas de Resumo e Extratos ainda mostravam valores fixos
marcados como "dados de exemplo", o botão "Importar extrato" só exibia uma mensagem e o
endereço da API era somente leitura. A abertura animada durava 3 s fixos, sem relação com
nenhum carregamento. A regra do projeto (ADR 0004) exige que somas, saldos e taxas sejam
calculados pelo backend, nunca pelo aplicativo.

## Decisão

- **Resumo com dados reais.** O Resumo consome `GET /v1/transactions/summary` e só exibe o
  que o `calculation_service.py` devolveu. A taxa de poupança chega em percentual e vira
  fração apenas para a barra de progresso. Há quatro estados: carregando, erro (com
  "Tentar novamente"), sem extratos (orienta a importar) e dados.
- **Importação pelo seletor de arquivos.** O botão usa `file_picker` (sem filtro de extensão, ver
  Consequências), valida que o arquivo é `.ofx` ou `.pdf` e envia o arquivo por `multipart/form-data` a `POST /v1/transactions/upload`. A
  mensagem de erro da API (`detail`) aparece para o usuário.
- **Lista de arquivos vinda do backend.** A tela de Extratos agrupa `GET /v1/transactions`
  por `source_file`, com a contagem de lançamentos e de duplicatas de cada arquivo. O app não
  guarda uma lista própria, então ela nunca diverge do que a API contabilizou.
- **Reenvio não duplica totais.** A API passou a comparar os lançamentos novos com os já
  importados (data, descrição, valor e tipo) e marca os repetidos como duplicata. Antes, só
  eram detectadas duplicatas dentro do mesmo arquivo, e reenviar um extrato dobrava os totais.
- **Endereço da API editável.** Ajustes ganha um campo com validação (só `http` ou `https`,
  com servidor, sem consulta nem fragmento), "Salvar endereço" e "Restaurar padrão". O valor
  fica no aparelho (ADR 0013) e é lido a cada chamada, então vale para Resumo, Extratos e
  chat sem reiniciar o app.
- **Abertura atrelada ao carregamento real.** A abertura espera o primeiro carregamento do
  resumo, com limite de 8 s. A barra avança até 90% com a animação e só completa quando os
  dados chegam; se a API não responder, o app abre e a tela de Resumo mostra o erro.

## Consequências

O primeiro quadro do Resumo já traz os números quando a API está no ar. Os lançamentos
continuam **na memória da API** (`_LOCAL_TRANSACTIONS`), então somem quando ela reinicia; o
texto da tela de Extratos diz isso. A persistência em SQLite dos lançamentos segue pendente
e está fora desta decisão. O seletor de arquivos do Android não conhece o tipo de `.ofx` e deixa o arquivo desabilitado
quando se filtra por extensão (observado em emulador). Por isso o app abre o seletor sem filtro
e valida a extensão depois da escolha, mostrando "Formato não suportado" para qualquer arquivo
que não seja `.ofx` ou `.pdf`. Importações grandes dependem do tempo limite de 60 s do envio.
