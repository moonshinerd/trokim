# 0009 — Síntese generativa local, camada LiteLLM e limites de fundamentação

- **Status:** Aceita
- **Data:** 13/11/2026
- **Requisitos / GQs:** RF03, RF05, RF06, RF10, RF17, RNF01, RNF02; GQ04, GQ05, GQ10, GQ11
- **Issues:** #23, #25, #26; experimento na #24
- **ADRs relacionadas:** [0002](0002-fastapi-sqlite-local.md), [0003](0003-rag-fontes-oficiais.md), [0004](0004-calculos-deterministicos.md), [0007](0007-banco-vetorial-embeddings.md), [0008](0008-material-comparativo-versionado.md)

## Contexto

O RAG da Semana 2 é extrativo: devolve o trecho oficial recuperado, sem redigir. A
Semana 3 exige respostas em linguagem natural ancoradas em evidências e uma comparação
com uma LLM pura e com um RAG ingênuo. A premissa local-first (ADR 0002) e a separação
entre cálculo e linguagem (ADR 0004) precisam ser mantidas. Também se quis poder trocar de
modelo por configuração, sem alterar o código, e não depender de um único fornecedor.

## Decisão

**Port e adaptadores.** O contrato `LLMProvider` (`api/app/models/llm_provider.py`) expõe
`generate(prompt, system_instruction, context_chunks, temperature, max_tokens)` e devolve
`LLMResponse`. Há três adaptadores em `api/app/clients/`, escolhidos por
`LLM_PROVIDER` na fábrica `get_llm_provider`:

- `litellm` (padrão): `LiteLLMProvider`, sobre o [LiteLLM](https://docs.litellm.ai).
  O modelo é definido só por configuração, no formato do LiteLLM
  (`ollama/qwen2.5`, `ollama/gemma4:26b`, `openai/gpt-4o-mini`, `openrouter/...`). Modelos
  locais não enviam dados a terceiros; modelos de nuvem exigem `LLM_API_KEY` e são uma
  escolha explícita de quem configura, fora da premissa local-first. A telemetria do
  LiteLLM é desligada. Para modelos Ollama, o raciocínio estendido ("thinking") fica
  desligado por padrão (`LLM_THINKING=false`), pois consumia os tokens e devolvia texto
  vazio em respostas curtas.
- `ollama`: cliente HTTP direto do Ollama local (`OllamaProvider`).
- `mock`: determinístico, para testes e CI sem dependência externa.

**Configuração** (`api/.env`, ver `.env.example`): `LLM_PROVIDER`, `LLM_MODEL`,
`LLM_API_BASE`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_TEMPERATURE`, `LLM_THINKING`,
`LLM_TITLE_MODEL` e `LLM_TITLE_TIMEOUT`.

**Orquestração.** `GenerationService` oferece três modos, com prompts versionados em
`api/app/prompts/` (ADR 0008):

| Modo | Recuperação | Prompt | Uso |
|---|---|---|---|
| `grounded` (produção) | Recuperação híbrida com limiar do serviço RAG | `prompt_trokim_grounded_v1.txt` | Resposta com citação por fonte e abstenção |
| `naive` | Mesmo serviço de recuperação, com limiar 0,05 e sem política de abstenção | `prompt_naive_rag_v1.txt` | Baseline do experimento |
| `pure` | Nenhuma | `prompt_llm_pure_v1.txt` | Baseline de LLM sem documentos |

**Abstenção.** No modo `grounded`, o serviço se abstém, sem chamar o modelo, quando a
consulta está fora do escopo (apostas, ações específicas, criptoativos) ou quando nenhuma
evidência passa do limiar de similaridade. A resposta é a `ABSTENTION_MESSAGE`, com
`status = abstained` e nenhuma evidência.

**Cálculo.** O modelo não calcula. Os prompts recebem `calculation_results`; na API, sem
resultado do serviço determinístico, é injetado "Nenhum resultado determinístico fornecido."
e o prompt manda reconhecer a limitação em vez de inventar valores. No experimento (#24),
os resultados vêm do `CalculationService` com entradas sintéticas.

**Endpoints** (`api/app/routers/v1/chat.py`):

- `POST /v1/chat/ask`: recuperação extrativa, sem LLM.
- `POST /v1/chat/generate`: síntese por modo. Se o modelo estiver indisponível, devolve
  `503` com mensagem clara. A geração é cancelada quando o cliente se desconecta
  (`run_while_connected`, `499`).
- `POST /v1/chat/title`: título curto para uma conversa (ADR 0014).

**Cliente móvel.** O app consome `/v1/chat/generate` (modo `grounded`) por padrão, com
tempo limite próprio e cancelamento da requisição; a opção "Respostas com IA" em Ajustes
(ADR 0013) alterna para `/v1/chat/ask`. O contrato é validado com rigor no app
(`AssistantReply`): modo, status, evidências e `model` precisam ser coerentes.

## Limites assumidos

- `grounded` **não** é comprovação automática de veracidade nem valida cada citação por
  afirmação: ancora a resposta nos trechos recuperados e instrui o modelo a citar. A
  revisão humana continua necessária (ver [relatório comparativo](../pesquisa/comparacao-llm-rag.md)).
- A abstenção não é universal: o filtro de escopo e o limiar não capturam todo caso
  adverso. O experimento registrou casos em que o Trokim respondeu quando deveria recusar.
- A qualidade depende do modelo escolhido. Os resultados publicados foram obtidos com
  Qwen 2.5 de 1,5 bilhão de parâmetros; modelos maiores podem se comportar de outro modo.
- O modo `naive` reutiliza a recuperação híbrida com limiar menor; não é um recuperador
  puramente denso.
- A cobertura da base é a de 20 documentos oficiais (ADR 0006). O suplemento do
  experimento (ADR 0008) não integra a API.

## Consequências

Trocar de modelo é uma mudança de configuração. O CI continua determinístico com o
`mock`. Há custo de latência: um modelo grande rodando em CPU leva dezenas de segundos
por resposta. Recomenda-se um modelo leve para títulos e outro, maior, para as respostas.
