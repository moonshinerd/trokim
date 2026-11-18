# 0017 — Perfis de banco, natureza do lançamento e privacidade dos Pix

- **Status:** Aceita
- **Data:** 18/11/2026
- **Requisitos / GQs:** RF01, RF02, RF09; GQ02, GQ03
- **Issues:** [#80](https://github.com/moonshinerd/trokim/issues/80)
- **ADRs relacionadas:** [0004](0004-calculos-deterministicos.md), [0005](0005-importacao-local-ofx-pdf.md), [0015](0015-dados-reais-importacao-e-endereco-da-api.md)

## Contexto

Testado com extratos reais do Nubank (conta e cartão), o parser genérico lia os arquivos, mas o
resultado enganava: acentos corrompidos (`Crédito` virava `CrÃ©dito`, pois o cabeçalho declara
CP-1252 e o conteúdo é UTF-8), quase todos os lançamentos em "outros", pagamento de fatura,
resgates e transferências próprias contados como receita ou despesa (e contados em dobro quando
a fatura do cartão também era importada), parcelas ignoradas e dados pessoais da contraparte dos
Pix (nome, CPF parcial, banco, agência e conta) no texto. No PDF, acentos e parcelas quebravam a
leitura, `1.250,00` virava `125,00` e compra sem sinal virava crédito.

## Decisão

1. **Perfil por banco** (`api/app/services/statement_profiles.py`). A detecção usa o conteúdo do
   OFX (`ORG`/`FID`/`BANKID` e o bloco `CCSTMTRS` ou `STMTRS`). Banco não reconhecido cai no
   parser genérico. Cada banco novo é um perfil novo, sem mexer nos demais.
2. **Decodificação robusta.** O arquivo é lido como UTF-8 e só cai para CP-1252 se falhar; o
   cabeçalho `CHARSET` é ignorado.
3. **Natureza do lançamento** (`TransactionNature`): compra, Pix enviado/recebido, pagamento de
   fatura, resgate e aplicação de investimento, transferência própria, estorno, tarifa, juros e
   outro. **Pagamento de fatura, resgate, aplicação e transferência própria não entram nos
   totais** (`NATURES_EXCLUDED_FROM_TOTALS`), o que evita contar duas vezes. **Estorno abate a
   despesa** em vez de virar receita. A conta continua determinística
   ([ADR 0004](0004-calculos-deterministicos.md)).
4. **Estabelecimento e privacidade.** O texto do lançamento é reescrito: o app e a API só
   expõem o nome do estabelecimento ou da contraparte e o tipo (`pessoa` ou `empresa`). Documento,
   banco, agência e conta **nunca** são guardados nem enviados ao chat ou à LLM.
5. **Parcelas** (`Parcela N/M`) viram `installment_number` e `installment_total`.
6. **Deduplicação por `FITID`** quando o banco fornece, combinado com conta, data, valor e tipo.
   O tipo entra na chave porque, no Nubank, uma compra e o estorno dela compartilham o mesmo
   `FITID`.
7. **Categorização por palavra inteira**, sem acento e por prioridade
   (`categorization_service.py`), em lugar da busca por trecho (que classificava `DROGASIL` como
   moradia por conter `gas`). A LLM não categoriza.
8. **PDF genérico corrigido**: acentos, milhar, sinal à frente ou atrás, sufixos `C`/`D`, parcelas
   e ano da data (nunca no futuro). Em fatura, valor sem sinal é compra; em extrato, é entrada.

## Consequências

- Os totais de receita e despesa passam a refletir dinheiro que entrou ou saiu de verdade.
- `LEDGERBAL` do arquivo é informado no relatório de importação, **sem** afirmar conferência:
  ele inclui o saldo anterior e não fecha com a soma dos lançamentos do período.
- `Resgate de empréstimo` e movimentações de nome desconhecido ficam como "outro" e continuam
  nos totais, até haver um exemplo que mostre a natureza correta.
- Pix para pessoas físicas fica em "outros": não há como inferir a finalidade sem o usuário, e é o
  que o ajuste de categoria no app (RF09) resolve.
- Os testes usam só arquivos sintéticos (`api/tests/nubank_samples.py` e
  `research/synthetic_data/generate_nubank_datasets.py`); nenhum extrato real entra no repositório.
