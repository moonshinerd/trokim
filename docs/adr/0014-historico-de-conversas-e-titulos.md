# 0014 — Histórico de conversas local e títulos gerados pelo LLM

- **Status:** Aceita
- **Data:** 13/11/2026
- **Requisitos / GQs:** RF16, RNF01; GQ01, GQ03, GQ05
- **Issue:** #44
- **ADRs relacionadas:** [0009](0009-sintese-generativa-local.md), [0013](0013-preferencias-locais-e-aba-de-ajustes.md)

## Contexto

O assistente mantinha uma única conversa em memória, perdida ao fechar o app. O time
pediu um histórico de conversas e que o LLM local desse um título curto a cada uma. Nada
pode sair do aparelho (RNF01), e o app não pode ficar sem título se o modelo falhar.

## Decisão

- **Armazenamento local.** As conversas (mensagens, evidências, título, datas) ficam em
  JSON no aparelho, via `shared_preferences`, atrás da interface `ConversationStore`.
  Dado corrompido é descartado sem impedir a abertura do app. Limite de 200 conversas.
  Trocar por SQLite exige apenas outra implementação da interface.
- **Título provisório.** Ao enviar a primeira pergunta, a conversa já nasce com a
  pergunta encurtada (até 40 caracteres, sem cortar palavra) como título, em itálico e com
  pontinhos pulsando enquanto o LLM nomeia.
- **Nomeação pelo LLM.** Depois da primeira resposta fundamentada, o app chama
  `POST /v1/chat/title`. O `TitleService` usa um prompt versionado
  (`prompt_titulo_v1.txt`), pede de 3 a 6 palavras e saneia a saída (uma linha, sem
  aspas nem markdown, sem terminar em artigo ou preposição). Pode usar um modelo leve e
  próprio (`LLM_TITLE_MODEL`, ex.: `qwen2.5:1.5b`), com tempo limite de 25 s.
- **Título de reserva.** Se o modelo falhar, demorar ou estiver em modo `mock`, a API
  devolve as primeiras palavras da pergunta (`source = fallback`). No app, se a chamada
  falhar, mantém-se o provisório, com no máximo duas tentativas.
- **Controle do usuário.** Renomear manualmente nunca é sobrescrito pelo LLM. Apagar pede
  confirmação. Abstenções não pedem título.
- **Fontes clicáveis.** Na resposta, os marcadores `[n]` viram o nome da fonte como link
  no texto, que rola até o cartão da fonte, abre e o destaca; o bloco "Fontes" com URLs
  soltas sai do texto, pois os cartões já trazem o link oficial.

## Consequências

O histórico funciona offline para leitura. A nomeação depende da API só para o título.
O armazenamento em um único JSON é simples, mas não escala a milhares de conversas.
O título gerado por um modelo pequeno pode ser genérico; o usuário pode renomear.
