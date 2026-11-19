# 0018 — Contas, períodos, transferências entre contas próprias e visões de caixa e competência

- **Status:** Aceita
- **Data:** 18/11/2026
- **Requisitos / GQs:** RF01, RF02, RF09, RF22 a RF26; GQ02, GQ03, GQ07, GQ09, GQ13
- **Issues:** [#80](https://github.com/moonshinerd/trokim/issues/80), [#82](https://github.com/moonshinerd/trokim/issues/82)
- **ADRs relacionadas:** [0004](0004-calculos-deterministicos.md), [0005](0005-importacao-local-ofx-pdf.md), [0017](0017-perfis-de-banco-e-natureza-do-lancamento.md)

## Contexto

A [ADR 0017](0017-perfis-de-banco-e-natureza-do-lancamento.md) resolveu a leitura de um arquivo
do Nubank. Com vários arquivos ao mesmo tempo, o mesmo dinheiro passou a aparecer em mais de um
lugar e os totais voltaram a enganar:

- quem tem conta pessoal e **Nubank Empresas** recebe dois OFX iguais no formato; o arquivo não
  diz de quem é a conta;
- a fatura **aberta** traz só os lançamentos até o dia em que foi baixada; reimportar quando ela
  fecha não pode somar os mesmos lançamentos de novo;
- o Pix da conta pessoal para a conta da empresa é gasto numa conta e receita na outra;
- o Pix que paga a fatura do cartão de **outro banco** é contado na conta e de novo nas compras
  da fatura;
- parcelas da mesma compra aparecem em várias faturas;
- o **Banco do Brasil** só entrega a fatura do cartão Ourocard em PDF, e o OFX da conta usa
  `NAME` para o tipo e `MEMO` para a contraparte, ao contrário do Nubank;
- a categorização por palavras deixa em "Outros" boa parte dos gastos de estabelecimentos
  pequenos, e a issue #80 previa uma tabela CNAE local, inviável porque o OFX não traz o CNAE.

## Decisão

1. **Conta cadastrada e dono.** Cada arquivo pertence a uma conta (banco + número, ou final do
   cartão no BB). O dono (`pessoal` ou `empresa`) é perguntado **uma vez** e lembrado. Antes de
   importar, `POST /v1/transactions/inspect` analisa o arquivo sem gravar nada: banco, tipo,
   período, dono provável (pelo cadastro, pelos documentos de outros arquivos, pelo pagamento da
   fatura e pelo nome do arquivo) e avisos de arquivo no lugar errado (pessoal × Empresas,
   conta × cartão, arquivo já importado noutra conta). O upload devolve **409** em conflito, até o
   usuário confirmar.
2. **Período e situação do arquivo.** `DTSTART`, `DTEND` e `DTSERVER` definem o período e a
   situação: fatura **aberta** ou **fechada**, extrato **parcial** ou **completo**. O usuário pode
   confirmar ("já fechou?") e ajustar o período. Reimportar o mesmo período **substitui** os
   lançamentos dele (resultado `atualizado`, `repetido` ou `novo`). A cobertura por conta aponta
   lacunas entre arquivos.
3. **Transferências entre contas próprias.** Ligação **certa** quando o Pix cita a conta de
   destino e ela é uma conta importada (as duas pontas saem dos totais e aparecem como **uma**
   transferência). Sem a conta no texto (como no BB), a outra ponta é ligada pelo mesmo valor até
   1 dia de diferença. O resto vira **sugestão** por valor e data, que o usuário confirma ou
   recusa; a confirmação ensina a identidade da contraparte (CNPJ normalizado entre bancos) e
   tudo pode ser desfeito. Pix que paga a fatura de outro banco vira **pagamento de fatura**.
4. **Visões.** **Gastos (competência):** a compra conta na data da compra e pagar a fatura não
   conta de novo. **Caixa:** só o que entrou e saiu das contas, com o pagamento da fatura no
   lugar das compras. O Resumo filtra por dono (Tudo, Pessoal, Empresas) e mostra o total por
   conta. Os números continuam calculados só no backend
   ([ADR 0004](0004-calculos-deterministicos.md)).
5. **Parcelamentos.** A mesma compra é agrupada entre faturas (estabelecimento, valor da parcela e
   total de parcelas); `GET /v1/installments` devolve parcela atual, quanto falta e a projeção
   mensal do que já está comprometido.
6. **Perfis do Banco do Brasil.** Fatura Ourocard em PDF (sinal invertido, `PARC NN/MM`,
   categorias do próprio banco, cartão pelo final e conferência com o total da fatura) e conta
   corrente em OFX "Money 2000+" em ISO-8859-1.
7. **Categoria escolhida pelo usuário.** Em lugar da tabela CNAE, o usuário corrige a categoria no
   app (`PATCH /v1/transactions/{uid}/category`). Por padrão a escolha vira **regra do
   estabelecimento** (nome normalizado, sem acento e sem caixa), aplicada aos lançamentos já
   importados e aos próximos arquivos; dá para mudar só um lançamento e remover a regra
   (`/v1/transactions/category-rules`). Movimentações internas não têm categoria e gasto não vira
   renda. Nada disso usa LLM.
8. **Arquivo por "Compartilhar".** No Android, o app aceita OFX e PDF enviados por
   "Compartilhar" ou "Abrir com" (intent filters `SEND` e `VIEW`). O `MainActivity` lê o arquivo e
   o entrega por um canal ao Flutter, que abre a aba Extratos e o fluxo de importação já com o
   arquivo escolhido. Nenhum dado sai do aparelho.

## Consequências

- Os totais deixam de contar duas vezes o dinheiro que só mudou de conta, e a fatura aberta pode
  ser reimportada quantas vezes for preciso.
- O app ganha telas de transferências, parcelamentos e categorias, mas não calcula nada: só
  mostra o que a API devolve e envia as decisões do usuário.
- As decisões do usuário (dono, confirmações, regras de categoria) ficam na memória da API, como
  os lançamentos ([ADR 0015](0015-dados-reais-importacao-e-endereco-da-api.md)), e somem quando
  ela reinicia. Persistir em SQLite fica para uma ADR futura.
- A meta de categorização da #80 (≥ 80% dos gastos com categoria) depende dos nomes reais dos
  estabelecimentos: a fatura do BB em PDF chega a cerca de 91% com as categorias do banco, e no
  Nubank o caminho é a regra aprendida com o usuário. A sugestão por LLM local fica como trabalho
  futuro, sempre como sugestão.
- O recebimento por "Compartilhar" só existe no Android; na web e em testes o canal não existe e
  o app segue sem ele.
- Tudo é testado com dados sintéticos (`research/synthetic_data/generate_nubank_datasets.py`,
  `api/tests/nubank_samples.py`, `api/tests/bb_samples.py`).
