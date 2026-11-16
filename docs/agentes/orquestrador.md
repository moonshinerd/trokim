# Orquestrador e Contratos

!!! info "Status: Planejado"
    Issue [#51](https://github.com/moonshinerd/trokim/issues/51). Esta página é preenchida no mesmo PR da implementação (regra: o MkDocs nunca fica defasado).

Coordena os quatro agentes e monta a trilha. Código previsto: `api/app/domain/agents.py` (contrato),
`api/app/services/agents/base.py` (protocolo `Agent`) e `api/app/services/agents/orchestrator.py`.

## Regras

1. **Research.** Se `abstain_reason` vier preenchido, encerra com `abstained` e uma resposta fixa, sem chamar o LLM.
2. **Analysis** só roda se a pergunta pede números (regra por palavras-chave); senão o passo é `skipped`.
3. **Communication** escreve o rascunho a partir de `evidences` e `calculations`.
4. **Validation** confere o rascunho. Com bloqueio e revisão disponível (`max_revisions`, padrão 1), volta ao Communication com os problemas; persistindo o bloqueio, encerra com `rejected` e uma mensagem segura.
5. Cada passo vira um `AgentStep` com a duração medida; uma falha inesperada vira `failed` e a resposta `rejected`.

## Como funciona na prática
*(A preencher na implementação: fluxo real, regras de `needs_analysis`, mensagens fixas e exemplos de trilha.)*

## Testes
*(A preencher: arquivos de teste e o que cobrem.)*

## Limitações
*(A preencher.)*
