# Passagem de bastão para outro agente (LLM)

> Leia este arquivo inteiro antes de mexer em qualquer coisa. Ele foi escrito em
> 13/11/2026 por um agente que precisou parar a sessão. Quem continua deve **apagar este
> arquivo** quando tudo abaixo estiver concluído (ou movê-lo para fora do PR antes do merge).

## 0. Regras do projeto (do `AGENTS.md`, inegociáveis)

- Tudo em **pt-BR** (commits, PRs, issues, docs, comentários).
- **Nunca** colocar `Co-Authored-By` de IA nem "Generated with ..." em commits, PRs ou issues.
- Identidade git: `git config user.name` = `moonshinerd` (já configurado neste repositório).
  Não invente credenciais.
- **Nunca** commitar na `main`; branches `feature/`, `fix/` ou `docs/`; PRs com `Closes #N`.
- **Nunca** commitar segredos nem dados reais (use `research/synthetic_data/`).
- Cálculo financeiro é 100% determinístico (`api/app/services/calculation_service.py`);
  a LLM nunca calcula.
- Antes de ações externas (push em branch de outra pessoa, fechar PR, mergear), **pergunte ao
  usuário** (é o dono do repositório; fala de forma informal e direta).

## 1. Situação atual

- **Branch local:** `juntar-47`, publicada em `origin/feat/24-benchmark-comparativo-llm-rag-trokin`
  (a branch do **PR #47**, da Rebeca). O usuário decidiu **juntar tudo nesse PR**.
- A branch contém a fusão de: PR **#47** (benchmark comparativo, Rebeca, issue #24), PR **#46**
  (chat generativo no app, Gabriel, issue #25) e PR **#43** (redesenho + histórico + LiteLLM,
  moonshinerd). Conflitos já resolvidos e testados.
- **PRs abertos relacionados:** #43 e #46 (duplicam conteúdo do #47 agora) e #47. **Não fechei
  nenhum**; decidir com o usuário (sugestão: mergear o #47 e fechar #43 e #46 como incorporados).
- **Issues deste trabalho:** #38 a #42 (redesenho), #44 (histórico + título), #45 (pendências
  do redesenho), #24, #25 e #26 (a #26 está defasada: ver seção 3).

### O que está pronto e validado (local)

| Verificação | Resultado |
|---|---|
| API: `cd api && uv run pytest` | 84 passaram |
| API: `ruff check` e `ruff format --check` | limpos |
| Pesquisa: `make research-test` | 59 passaram |
| App: `cd mobile && flutter test` | 90 passaram |
| App: `dart format --output=none --set-exit-if-changed lib test` | ok |
| App: `flutter analyze --no-fatal-infos` | ok (restam ~36 infos, quase todos a depreciação de `material.dart`) |
| Site: `uvx zensical build --strict` | ok |

**O CI no GitHub ainda não rodou sobre esta fusão**: confira os checks do PR #47 depois do push.

## 2. O que foi construído (resumo técnico)

- **Identidade visual do app e do MkDocs:** paleta Champagne `#FAEBD7`, Tidewater `#2F4F4F`,
  Fortuna Gold `#DAA520`; tema claro/escuro seguindo o sistema; Plus Jakarta Sans embarcada;
  logo = cabeça da onça-pintada numa mini-moeda; abertura com moeda 3D girando; aba **Ajustes**;
  rolagem sem esticar. ADRs 0011, 0012 e 0013.
- **Mascote:** vetor CC0 "Jaguar SVG" (AntumDeluge, OpenGameArt), estilizado. Arquivos trocáveis
  em `mobile/assets/brand/` (`mascot_body.png`, `mascot_head.png`; ver o `LEIA-ME.md` de lá).
- **LiteLLM** (`api/app/clients/litellm_provider.py`): modelo trocável só por `.env`.
  `LLM_THINKING=false` por padrão (modelos Ollama com "thinking" devolviam texto vazio).
- **Título de conversa pelo LLM:** `POST /v1/chat/title`, `TitleService`, prompt
  `prompt_titulo_v1.txt`, modelo leve opcional `LLM_TITLE_MODEL`, título de reserva determinístico.
- **`POST /v1/chat/generate`:** agora responde `503` claro se o modelo falha; cancela quando o
  cliente desconecta (código do Gabriel, `request_lifecycle.py`).
- **App:** histórico de conversas local (`ConversationStore`, `shared_preferences`), título
  provisório (a pergunta) que o LLM substitui, renomear/apagar, **fontes clicáveis** (o `[n]` da
  resposta vira o nome da fonte como link que abre o cartão), interruptor "Respostas com IA" em
  Ajustes (liga `/chat/generate`; desligado usa `/chat/ask`). Modelos tipados e estritos do
  Gabriel (`AssistantReply`, `AssistantStatus`) foram mantidos; o histórico serializa por cima.
- **Benchmark da Rebeca** (`research/rag_benchmark/run_comparison.py`): agora usa a camada
  LiteLLM por padrão (`--provider litellm --model ollama/qwen2.5:1.5b`).
  A impressão digital de `eval_rag.py` passou a incluir só os clientes de recuperação, e os
  snapshots `research/rag_benchmark/results/{current,baseline}.json` foram regenerados
  (métricas idênticas; só a proveniência mudou).
- **CI:** o job `mobile` (Gabriel) usa `flutter analyze --no-fatal-infos` e `pub get
  --enforce-lockfile`; o `mobile/pubspec.lock` foi atualizado e commitado.
- **ADRs novas:** 0009 (síntese generativa local + LiteLLM), 0010 (CI hospedado), 0011
  (identidade visual), 0012 (mascote), 0013 (preferências/Ajustes), 0014 (histórico + títulos).
  Requisitos v1.2.0: RF15, RF16, RF17, RNF10, RNF11.
- **Relatório comparativo:** `docs/pesquisa/comparacao-llm-rag.md`, escrito só com os dados
  dos artefatos da Rebeca (`artifacts/research/comparison_report.md` e `comparison_audit.md`).

## 3. Pendências, em ordem de prioridade

### A. Terminar a documentação da issue #26 (iniciada, incompleta)

Já feito: relatório, ADRs 0009 a 0014, requisitos, índice de ADRs, menu do MkDocs.
**Falta, e a issue pede:**

1. `docs/arquitetura/index.md` e `docs/arquitetura/mapa-do-sistema.md`: descrever o fluxo real
   (recuperação → modo → abstenção → geração → evidências), diferenciar `/v1/chat/ask`
   (extrativo) de `/v1/chat/generate` (generativo) e `/v1/chat/title`; mostrar a camada LiteLLM
   e o histórico no diagrama Mermaid. O diagrama já tem "Design System" e "Ajustes locais".
2. `docs/apresentacao.md`: o painel ainda diz "45/45 testes" (desatualizado: API 84, pesquisa 59,
   app 90) e descreve a aplicação como só extrativa; incluir a comparação das três abordagens
   com os casos reais (C04, C07, C17, C26, C29, C30 do relatório). Não inventar exemplos.
3. `docs/guia-de-uso.md`: a seção "Síntese Generativa Local (Qwen via Ollama)" está defasada.
   Documentar `LLM_PROVIDER`/`LLM_MODEL`/`LLM_TITLE_MODEL`/`LLM_THINKING`, o `.env.example`,
   `ollama pull qwen2.5:1.5b`, o `/v1/chat/title` e o interruptor "Respostas com IA".
4. `docs/planejamento.md`: o checklist da Semana 3 está todo `[ ]`. Marcar o que existe de
   fato (prompts, gabarito, métricas, síntese, endpoint, cartões, relatório parcial, ADR 0008 e
   0009) e **não** declarar a Semana 3 concluída: falta a homologação do chat no Android
   (ver `mobile/VALIDACAO_CHAT_GENERATIVO.md`, do Gabriel) e a publicação das respostas brutas.
5. `docs/atas/index.md`: **não criar `ata04.md`**: a issue manda registrar validação só se a
   reunião ocorreu. Apenas atualizar o estado das issues #20 a #26.
6. `mobile/README.md`: registrar histórico, título pelo LLM, fontes clicáveis, "Respostas com IA"
   e a estrutura de `core/settings`, `core/widgets`, `assets/brand`.
7. `docs/referencias.md`: já tem "Créditos de Arte"; conferir se falta algo.

### B. Atualizar issues e o PR (precisa do ok do usuário para ações externas)

- **Issue #26:** o corpo está defasado: diz "LiteLLM não está implementado" (agora está, ver
  ADR 0009), "#24 e #25 abertas" (entram neste PR) e "PR #35 aberto" (foi fechado e o conteúdo
  migrou). Atualizar a tabela "Estado atual verificado" e marcar os critérios de aceite
  cumpridos **com evidências**; deixar desmarcado o que depende de ação humana (publicação das
  respostas brutas, homologação no Android, publicação após o merge).
- **PR #47:** retitular e reescrever o corpo (pt-BR): cobre #24, #25, #26 e #38 a #44, com
  `Closes #N` para cada uma e os pontos de atenção da seção 5. Não colocar "Generated with".
- **Issue #25:** só encerrar depois que o usuário homologar no Android.

### C. Ideias novas que o usuário pediu (ainda não feitas)

1. **Protótipo visual HTML no MkDocs**, "como um protótipo do Figma": uma página `.html`
   (ou componente incorporado) que reproduz as telas do app (Resumo, Extratos, Assistente com
   histórico e fontes clicáveis, Cenários, Ajustes), com a paleta e os temas claro/escuro e
   transições. Sugestão: `docs/prototipo/` com HTML/CSS/JS estáticos e iframe em
   `docs/prototipo.md`; **sem dependência de CDN** (premissa local-first) e com dados
   sintéticos. Não reintroduzir o antigo `apresentacao_trokim.html` na raiz.
2. **Fonte do MkDocs:** `mkdocs.yml` usa `font: text: Plus Jakarta Sans`, que o tema Material
   baixa do Google Fonts (quebra a premissa local-first). Embarcar a fonte no site
   (`docs/assets/fonts/` + `@font-face` em `docs/stylesheets/extra.css` e `font: false` no tema).
3. **Issue #45** (pendências do redesenho): Resumo com dados reais do backend
   (`/v1/transactions/summary`), importação de extratos pelo `file_picker`, endereço da API
   editável em Ajustes, barra de carregamento real na abertura.
4. Migrar `package:flutter/material.dart` para `material_ui` quando for conveniente
   (depreciação no Flutter 3.50; hoje só gera infos).

### D. Dívidas conhecidas (não esconder)

- O CI do Flutter ainda não foi executado sobre esta fusão.
- Respostas brutas do benchmark (`comparison_results.json`) **não** estão versionadas
  (`/artifacts/research/` está no `.gitignore`; só `comparison_report.md` e
  `comparison_audit.md` foram adicionados à força). A issue #26 exige local durável.
- A auditoria do benchmark foi assistida por agente e não cega; modelo de 1,5 B; execução única.
- A tela Resumo e a lista de Extratos usam dados fixos, marcados como "dados de exemplo".
- Resposta do Gemma 26B leva ~50 s; prefira um modelo menor para o dia a dia.
- A numeração das ADRs foi reorganizada: as minhas (antes 0009 a 0012) viraram 0010 a 0013 para
  a **0009** ser a de síntese generativa, como a issue #26 pede. Nenhuma foi publicada antes.

## 4. Ambiente da máquina original (o seu pode ser outro; refaça se precisar)

Nada disso vai para o repositório; são configurações locais.

- **Flutter 3.50:** instalado por git em `~/flutter-sdk` (`export PATH=$HOME/flutter-sdk/bin:$PATH`).
  Homebrew não tinha permissão de escrita.
- **JDK 17** em `~/jdk/jdk-17*/Contents/Home` e **Android SDK** em `~/Library/Android/sdk`
  (`JAVA_HOME`, `ANDROID_HOME`; AVD `trokim` = Pixel 7, Android 35, ARM).
  Emulador: `emulator -avd trokim -no-audio -gpu host`. App id: `br.com.trokim.trokim`.
  Instalar: `cd mobile && flutter build apk --debug && adb install -r build/app/outputs/flutter-apk/app-debug.apk`.
  A API é vista pelo emulador em `http://10.0.2.2:8000/v1`.
- **Ollama** com os modelos `gemma4:26b` (grande, lento) e `qwen2.5:1.5b` (leve).
- **`api/.env`** (ignorado pelo git) usava `LLM_MODEL=ollama/gemma4:26b`, `LLM_TIMEOUT=300`,
  `LLM_TITLE_MODEL=ollama/qwen2.5:1.5b`. O `api/.env.example` documenta todas as variáveis.
- Subir a API: `DEBUG=false ENVIRONMENT=development make api-run` (porta 8000).
  Subir a documentação: `uvx zensical serve -a localhost:8001`.
- `uv` em `~/.local/bin` (`export PATH=$HOME/.local/bin:$PATH`).
- Python do sistema não tem certificados SSL: para baixar coisas use `curl`.

## 5. Pontos de atenção para o PR e para quem revisa

- O `mobile/pubspec.lock` foi **atualizado de propósito** (o CI usa `--enforce-lockfile`).
- Dependência nova no app: `shared_preferences`. Dependência da API: `litellm` (já estava).
- O mascote vem de arte **CC0** (créditos em `docs/referencias.md` e `mobile/assets/brand/LEIA-ME.md`).
- Os testes do app foram escritos para o contrato estrito do Gabriel: a resposta simulada
  precisa de `query`, `mode: grounded`, `model`, `status` e evidências coerentes.
- `flutter test` não valida o visual; verifique no emulador as telas de chat, histórico e
  fontes clicáveis antes de dar o aceite da #25.

## 6. Como validar tudo de uma vez

```bash
cd api && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd .. && make research-test && uvx zensical build --strict
cd mobile && flutter pub get --enforce-lockfile \
  && dart format --output=none --set-exit-if-changed lib test \
  && flutter analyze --no-fatal-infos && flutter test
```
