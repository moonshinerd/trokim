# 0009 — CI em runners hospedados do GitHub Actions

- **Status:** Aceita
- **Data:** 13/11/2026
- **Requisitos / GQs:** RNF06, RNF08; GQ08
- **PR:** #33

## Contexto

O CI rodava em um runner *self-hosted* macOS, preso a uma máquina específica do
time. Quando ela ficava offline ou sem créditos, nenhum PR era validado, e a
reprodutibilidade dos resultados dependia do ambiente local de quem hospedava.

## Decisão

Executar os workflows `ci.yml` e `docs.yml` em `ubuntu-latest`. O cache do
FastEmbed passa a usar `${{ github.workspace }}/.fastembed`, alinhado à variável
`FASTEMBED_CACHE_PATH`. Nenhuma etapa muda: `ruff`, `pytest`, benchmark do
`research/` e `zensical build --strict`.

## Consequências

Qualquer PR é validado em ambiente limpo e idêntico para todos, sem depender de
uma máquina do time. Erros que antes só apareciam em Linux agora são detectados
no PR. O CI **não executa `flutter test`**: o mobile continua sendo validado
apenas localmente, e um job de Flutter é uma evolução futura.
