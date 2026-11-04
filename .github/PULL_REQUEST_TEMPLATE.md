## Descrição
<!-- O que muda e por quê. Se for uma decisão arquitetural ou técnica (ex.: novo cálculo, threshold RAG, lib), registre a motivação aqui. -->

## Issue relacionada
<!-- Ex.: Closes #N -->
Closes #

## Área afetada
- [ ] `mobile/` (Aplicativo Android em Flutter)
- [ ] `api/` (FastAPI, routers, serviços ou banco SQLite)
- [ ] `research/` (Base oficial RAG, benchmarks ou dados sintéticos)
- [ ] `docs/` (Documentação Zensical, atas ou ADRs)
- [ ] Infra (Docker, CI/CD, Workflows)

## Como testar
<!-- Passos detalhados para reproduzir e validar a mudança -->
1. 
2. 

## Checklist de Qualidade
- [ ] Branch criada a partir da `main` no padrão `feature/*`, `fix/*`, `docs/*` ou `chore/*`
- [ ] Não expõe segredos, credenciais bancárias ou tokens de API
- [ ] Não utiliza dados financeiros reais de pessoas (apenas sintéticos em `research/synthetic_data/`)
- [ ] Se mexeu em `api/` ou `research/`: `make test` e `make lint` passaram com sucesso
- [ ] Se mexeu em `docs/`: `make docs-build` compilou sem avisos (`--strict`)
- [ ] Se alterou regras de negócio ou contratos de domínio (`app/domain/`): documentou o motivo
- [ ] Mensagens de commit limpas, sem trailers ou menções sintéticas de IA (conforme `AGENTS.md`)
