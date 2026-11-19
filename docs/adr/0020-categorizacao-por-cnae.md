# 0020 — Categorização por atividade econômica (CNAE) com os dados abertos do CNPJ

- **Status:** Aceita
- **Data:** 18/11/2026
- **Requisitos / GQs:** RF09, RNF01; GQ03, GQ07, GQ11
- **Issues:** [#80](https://github.com/moonshinerd/trokim/issues/80)
- **ADRs relacionadas:** [0004](0004-calculos-deterministicos.md), [0017](0017-perfis-de-banco-e-natureza-do-lancamento.md), [0018](0018-contas-periodos-transferencias-e-visoes.md)

## Contexto

A meta da [#80](https://github.com/moonshinerd/trokim/issues/80) é ter ao menos 80% dos gastos
com categoria. As regras por palavra acertam bem as marcas conhecidas, mas deixam em "Outros" as
empresas pequenas e regionais, que são a maior parte dos Pix para empresas. A
[ADR 0018](0018-contas-periodos-transferencias-e-visoes.md) adiou a tabela CNAE e colocou a
correção pelo usuário no lugar; esta ADR retoma a CNAE agora que há fonte e medição.

Não existe base pública rotulada de lançamentos bancários brasileiros (texto do extrato com a
categoria). O que existe é o cadastro de empresas: a Receita Federal publica os **Dados Abertos do
CNPJ**, com o nome fantasia e a **atividade principal (CNAE)** de cada estabelecimento, e o IBGE
publica a tabela CNAE 2.3. No Nubank, o texto do Pix para empresa traz o CNPJ completo do
recebedor: nos extratos de teste do desenvolvedor, 36 de 64 débitos.

## Decisão

1. **Tabela CNAE → categoria** versionada em `api/app/services/cnae_categories.py`, por prefixo
   (subclasse, classe, grupo ou divisão; vale o mais longo), com as mesmas convenções das regras
   por palavra ([Categorias](../arquitetura/categorias.md)). Indústria, atacado e agro ficam em
   "Outros": não dizem nada sobre o gasto de uma pessoa.
2. **Índice CNPJ → categoria, local e opcional.** `make cnpj-download` baixa os arquivos de
   Estabelecimentos e a tabela de CNAEs (Empresas e Sócios não, porque trazem nomes de pessoas)
   para uma pasta fora do repositório. `make cnpj-index` gera `api/data/cnpj/raizes.npy` e
   `categorias.npy`: a raiz do CNPJ de cada empresa ativa e a categoria da atividade da matriz.
   A API abre os arquivos por memory-map, sem carregá-los na RAM. **O índice não vai para o git**
   (é grande e muda todo mês); sem ele, nada muda.
3. **Dicionário de redes, versionado** em `api/app/data/marcas_cnpj.json`: nome fantasia usado por
   20 ou mais estabelecimentos ativos da mesma raiz, com a categoria da **atividade mais comum
   entre essas lojas**. A atividade da matriz não serve aqui: em muitas redes a matriz é
   escritório ou holding, e a primeira geração pôs supermercados (G Barbosa, Bretas, Prezunic) em
   serviços. Ficam de fora os nomes genéricos ("farmácia", "posto central", "avenida"), unidades de
   órgãos ("diretoria regional de...") e os nomes que aparecem em redes de categorias diferentes.
   MEI e empresário individual não entram, porque têm um estabelecimento só e o nome deles
   costuma ser o de uma pessoa.
4. **Ordem:** regra do usuário, regras por palavra, dicionário de redes, CNAE pelo CNPJ e, por
   último, a categoria do banco (fatura do BB). O CNPJ só é consultado em **saídas** e só quando é
   de empresa (14 dígitos); CPF nunca é consultado nem guardado como chave.
5. **Sem LLM.** A categoria continua determinística e auditável
   ([ADR 0004](0004-calculos-deterministicos.md)).

## Alternativas consideradas

- **Só a correção pelo usuário** ([ADR 0018](0018-contas-periodos-transferencias-e-visoes.md)):
  continua valendo, mas deixa ao usuário um trabalho que dados públicos resolvem.
- **Consultar o CNPJ em uma API externa** (BrasilAPI, ReceitaWS): mandaria a lista de empresas em
  que a pessoa gasta para terceiros, contra a premissa local-first ([RNF01](../requisitos.md)).
- **LLM para categorizar:** variável entre execuções e difícil de auditar; fica, no máximo, como
  sugestão que o usuário aceita, em trabalho futuro.
- **Lista de MCC das bandeiras:** o extrato do Nubank e do BB não traz o MCC.

## Consequências

- Pix para empresas pequenas passa a ter categoria sem o usuário fazer nada, desde que o banco
  informe o CNPJ. No BB, que não informa, só o dicionário de redes ajuda.
- A atividade cadastrada pode não ser o que a pessoa comprou (um posto que vende café, uma
  farmácia que vende chocolate). A correção pelo usuário continua sendo a palavra final.
- O índice precisa ser refeito quando a Receita publica um novo mês. Isso é opcional: empresas
  novas só ficam sem categoria até a próxima geração.
- Download de cerca de 5 GB uma vez (17,5 GB de CSV, lidos direto dos zips). A geração leva cerca
  de 30 minutos e usa até 1,5 GB de RAM; o índice ocupa 130 MB em disco (27,3 milhões de empresas
  ativas) e quase nada de RAM na API, por memory-map.

## Resultados

Medidos nos conjuntos versionados (`api/tests/data/`) e nos extratos reais do desenvolvedor, só
localmente, com o índice de novembro de 2026 (27,3 milhões de empresas ativas) e 746 redes no
dicionário. Detalhes em [Categorias](../arquitetura/categorias.md).

| Medida | Antes | Depois |
|---|---:|---:|
| Validação escrita sem olhar as regras (111 casos, meta de 80%) | 82,9% na 1ª medição | 99,1% |
| Variações de formato de vários bancos (259 casos) | — | 98,8% |
| Gastos reais com categoria | 56% (só regras) | **67%** |
| Gastos reais com categoria, sem Pix para pessoas | 75% | **89%** |
| Valor dos gastos reais com categoria | 28% | **62%** |

A meta de 80% da [#80](https://github.com/moonshinerd/trokim/issues/80) foi atingida no que dá para
inferir (89% sem Pix para pessoas) e no conjunto de validação, mas **não no total** (67%): os Pix
para pessoas físicas são 26 dos 35 gastos que ficaram em Outros, e para eles só a correção pelo
usuário resolve. O ganho veio todo do CNAE, nos Pix do Nubank para empresas; o dicionário de redes
não mudou nada nesses extratos. A primeira geração do dicionário usava a atividade da matriz e foi
corrigida (ver Decisão, item 3).
