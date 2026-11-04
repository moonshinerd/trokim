# AGENTS.md

Guia e regras operacionais para agentes autônomos de IA trabalhando no repositório **Trokim**.

---

## 1. Regras Obrigatórias e Inegociáveis

- **Proibição Absoluta de Atribuição de IA:**
  - **NUNCA** adicionar trailers como `Co-Authored-By: Claude`, `Co-Authored-By: Gemini`, `Co-Authored-By: Cursor` ou qualquer menção a IA em mensagens de commit.
  - **NUNCA** adicionar frases como `"Generated with AI"`, `"Generated with Antigravity"`, ou qualquer identificação de ferramenta sintética em commits, Pull Requests, issues ou documentação.
- **Identidade Estrita nos Commits:**
  - Cada contribuição deve refletir a identidade humana do membro do projeto configurada no git.
  - Antes de executar qualquer commit, confira se `git config user.name` e `git config user.email` estão definidos. Se estiverem vazios ou apontando para usuários genéricos de máquina (como `aluno1 <aluno1@PBIA01.local>`), **pergunte ao usuário** o nome e e-mail antes de commitar e defina apenas localmente no repositório (`git config user.name "..."`).
  - Nunca invente credenciais nem commite sem confirmação de autoria.
- **Fluxo de Branches e Git:**
  - **NUNCA** commitar diretamente na branch `main`.
  - Crie sempre uma branch com o padrão `feature/<descricao-curta>`, `fix/<descricao-curta>` ou `docs/<descricao-curta>`.
  - Abra Pull Requests com referências explícitas às issues atendidas (ex.: `Closes #N`).
- **Segurança e Privacidade (LGPD):**
  - **NUNCA** commitar segredos, chaves de API (`OPENAI_API_KEY`, tokens OpenRouter), senhas ou credenciais bancárias.
  - **NUNCA** commitar dados financeiros reais de usuários (extratos, CPFs, nomes). Use exclusivamente geradores de dados sintéticos localizados em `research/synthetic_data/`.
- **Idioma Padrão:**
  - Toda a documentação, mensagens de commit, nomes de Pull Requests, issues e comentários de código devem ser redigidos em **Português do Brasil (pt-BR)**.

---

## 2. Visão Geral do Projeto (Trokim)

O **Trokim** é um assistente financeiro pessoal de código aberto desenvolvido no âmbito do **Challenge 2 (Big Idea: Qualidade de Vida / TIC-IA 2026)**.

- **Problema:** Pessoas que utilizam múltiplas contas e cartões sofrem com a dispersão de dados, falta de previsibilidade de gastos e dificuldade em tomar decisões orçamentárias alinhadas à sua qualidade de vida.
- **Essential Question:** *"Como a inteligência artificial pode ajudar as pessoas a compreender e planejar suas finanças pessoais, tomando decisões informadas sem comprometer sua qualidade de vida?"*
- **Premissa de Privacidade:** Processamento local-first. O usuário importa seus próprios extratos (OFX/PDF) e os dados ficam sob seu controle, armazenados localmente em SQLite.
- **Raciocínio Determinístico vs. IA:**
  - Cálculos financeiros (totais, somatórios, balanço, médias, projeções) são **100% determinísticos** e calculados por código em `api/app/services/calculation_service.py`. A LLM **nunca** calcula saldos ou orçamentos; ela recebe os números computados e fornece explicações pedagógicas.
  - O mecanismo **RAG (Retrieval-Augmented Generation)** fundamenta as orientações financeiras em materiais institucionais oficiais (Banco Central do Brasil, CVM, CFPB). Quando não houver evidência suficiente, o agente deve se abster de opinar.

---

## 3. Arquitetura do Repositório

```text
trokim/
├── AGENTS.md                  # Regras operacionais para agentes de IA
├── Makefile                   # Automação de tarefas (setup, lint, test, docs)
├── mkdocs.yml                 # Configuração do site de documentação (Material)
├── docs/                      # Documentação viva do projeto
│   ├── index.md               # Apresentação do Trokim
│   ├── planejamento.md        # Roadmap de 7 semanas do CBL e sprints
│   ├── requisitos.md          # Tabela MoSCoW, RFs, RNFs e rastreabilidade
│   ├── pesquisa/              # Guiding Questions (GQ01 a GQ10) e matrizes de risco
│   ├── arquitetura/           # Diagramas C4, fluxo de dados e pipeline RAG
│   └── adr/                   # Architecture Decision Records (0001 a 0005+)
├── overrides/                 # Customizações HTML do tema MkDocs
├── api/                       # Backend FastAPI (Python 3.12+, uv)
│   ├── pyproject.toml         # Dependências da API e configurações de lint/teste
│   ├── app/
│   │   ├── domain/            # Entidades de negócio puras (Transaction, Budget, Evidence)
│   │   ├── models/            # Esquemas de persistência e interfaces abstratas (Ports)
│   │   ├── clients/           # Adaptadores de banco (SQLite) e provedores de IA
│   │   ├── services/          # Regras de aplicação (parsing OFX/PDF, cálculos, RAG)
│   │   ├── routers/v1/        # Endpoints HTTP finos (sem lógica de negócio)
│   │   ├── prompts/           # Prompts versionados (<nome>_v<N>.txt)
│   │   └── core/              # Configurações de ambiente e segurança
│   └── tests/                 # Testes unitários e de integração (pytest)
├── mobile/                    # Aplicativo Android em Flutter (Dart)
│   ├── pubspec.yaml           # Dependências do app
│   └── lib/
│       ├── core/              # Temas, constantes e cliente HTTP da API
│       ├── features/          # Módulos verticais (extratos, dashboard, chat, simulações)
│       └── main.dart          # Ponto de entrada do app Flutter
├── research/                  # Laboratório de dados e avaliação da Semana 2+
│   ├── knowledge_base/        # Documentos oficiais (BCB, CVM, CFPB) para o RAG
│   ├── synthetic_data/        # Scripts de geração de extratos OFX e faturas PDF sintéticas
│   └── rag_benchmark/         # Avaliação de recuperação, precisão e abstenção
└── deploy/                    # Configurações de execução e Docker Compose
```

---

## 4. Diretrizes de Desenvolvimento de Código

### Backend (`api/`):
- Padrão em camadas: `routers → services → domain`.
- O pacote `domain` deve ser agnóstico de infraestrutura, bancos de dados e frameworks externos.
- Use tipagem estrita com Pydantic v2 e validações de esquema.
- Formatação e linter via `ruff check` e `ruff format`.
- Testes automatizados com `pytest` cobrindo cálculo financeiro, extração de OFX e recuperação RAG.

### Mobile (`mobile/`):
- Arquitetura por funcionalidades (*feature-first*), separando apresentação, controladores de estado e repositórios.
- Interface limpa, responsiva e focada na usabilidade para Android.
- Nenhuma chave de API ou segredo de servidor deve ser embutido no código do Flutter.

### Documentação e Rastreabilidade (`docs/`):
- Todo Requisito Funcional (**RF**) e Não Funcional (**RNF**) deve referenciar sua **Guiding Question (GQ)** de origem.
- Decisões estruturais significativas devem ser registradas como uma nova **ADR** em `docs/adr/`.
- Mantenha o diagrama Mermaid de arquitetura atualizado a cada grande mudança.

---

## 5. Comandos Rápidos

```bash
make setup        # Configura ambiente virtual uv e dependências
make test         # Executa bateria de testes na api e research
make lint         # Executa ruff para checagem estática
make format       # Aplica auto-formatação
make docs-serve   # Inicia servidor local de documentação MkDocs (:8001)
make api-run      # Inicia backend FastAPI (:8000)
```
