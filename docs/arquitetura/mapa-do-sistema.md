# Mapa do Sistema

Visão visual das interações, componentes e fluxos de dados no **Trokim**.

---

## 1. Diagrama de Componentes C4 (Nível 2)

```mermaid
graph TD
    subgraph "Dispositivo Android (Mobile)"
        FlutterApp["App Flutter Trokim<br/>(UI Material 3 / Dart)"]
        StateManagement["Gerenciamento de Estado<br/>(Feature-First / Repositories)"]
        DesignSystem["Design System<br/>(Tema claro/escuro, movimento, mascote)"]
        Settings["Ajustes locais<br/>(shared_preferences)"]
        History["Histórico de conversas<br/>(no aparelho)"]
        AgentTrace["Modo multiagente opcional<br/>(modelos Dart e trilha por resposta)"]
        ShareIntent["Receber arquivo por Compartilhar<br/>(MainActivity + canal)"]
        FlutterApp --> StateManagement
        FlutterApp --> DesignSystem
        FlutterApp --> Settings
        FlutterApp --> History
        FlutterApp --> AgentTrace
        ShareIntent --> FlutterApp
    end

    subgraph "Serviço Backend Local (Python / FastAPI)"
        APIEntry["Routers v1<br/>(/transactions, /accounts, /statements, /installments,<br/>/transfers, /backup, /chat, /budgets, /health, /agents)"]
        AgentAsk["POST /v1/agents/ask<br/>(MultiAgentResponse)"]
        
        Vision["Portas de leitura de imagem<br/>(OcrProvider: RapidOCR local;<br/>VisionProvider: LiteLLM, opcional)"]
        Parser["Parser de Documentos<br/>(OFX & PDF, perfis Nubank e BB)"]
        Library["Biblioteca local<br/>(contas, períodos, detector,<br/>transferências, parcelas, regras de categoria)"]
        CalcService["Motor de Cálculo Determinístico<br/>(Totais, Balanço, 50-30-20)"]
        RAGService["Mecanismo RAG Híbrido<br/>(Dense + Sparse TF-IDF)"]
        GenService["Serviço de Síntese Generativa<br/>(GenerationService)"]
        TitleSvc["Título de conversa<br/>(TitleService)"]
        
        subgraph "Sistema Multiagente (ADR 0016)"
            Orchestrator["Orquestrador Determinístico"]
            ResearchAgent["Research Agent<br/>(evidências & escopo)"]
            AnalysisAgent["Analysis Agent<br/>(cálculos determinísticos)"]
            CommAgent["Communication Agent<br/>(redação em pt-BR)"]
            ValidAgent["Validation Agent<br/>(auditoria defensiva)"]
        end
        
        DomainCore["Entidades de Domínio Puro<br/>(Transaction, Budget, EvidenceChunk, MultiAgentResponse)"]
        
        subgraph "Persistência Local (SQLite)"
            Mem[(Memória da API<br/>Lançamentos da sessão)]
            VecDB[(SQLite-Vec<br/>Tabela Virtual vec0)]
        end

        subgraph "Provedores de Inferência (LLM)"
            LiteLLM["LiteLLMProvider<br/>(padrão; ex.: ollama/qwen2.5:1.5b)"]
            OllamaClient["OllamaProvider<br/>(cliente direto)"]
            MockLLM["MockLLMProvider<br/>(Testes & CI)"]
        end
        
        APIEntry --> Parser
        Vision -.->|foto ou PDF escaneado, Semana 5| Parser
        APIEntry --> Library
        Library --> Parser
        Library --> DomainCore
        APIEntry --> CalcService
        APIEntry --> RAGService
        APIEntry --> GenService
        APIEntry --> TitleSvc
        APIEntry --> Orchestrator
        AgentTrace -. "habilitado em Ajustes" .-> AgentAsk
        AgentAsk --> Orchestrator
        
        Orchestrator --> ResearchAgent
        Orchestrator --> AnalysisAgent
        Orchestrator --> CommAgent
        Orchestrator --> ValidAgent
        
        ResearchAgent --> RAGService
        AnalysisAgent --> CalcService
        CommAgent --> LiteLLM
        CommAgent --> OllamaClient
        CommAgent --> MockLLM
        ValidAgent --> DomainCore
        
        Parser --> DomainCore
        CalcService --> DomainCore
        RAGService --> DomainCore
        GenService --> RAGService
        GenService --> LiteLLM
        GenService --> OllamaClient
        GenService --> MockLLM
        TitleSvc --> LiteLLM
        
        DomainCore --> Mem
        RAGService --> VecDB
    end

    subgraph "Base de Conhecimento e Embeddings"
        KnowledgeBase["20 Documentos Oficiais<br/>(BCB, CVM, CFPB, ANPD)"]
        Embedder["FastEmbed Local<br/>(MiniLM-L12-v2 384d)"]
        
        KnowledgeBase --> RAGService
        Embedder --> RAGService
    end

    StateManagement -->|HTTP / JSON Local| APIEntry
```

---

## 2. Fluxo de Importação de Extratos e Resumo

Pagamento de fatura, resgates e transferências próprias ficam fora dos totais e o estorno abate a despesa ([ADR 0017](../adr/0017-perfis-de-banco-e-natureza-do-lancamento.md)). Contas, situação do período, transferências entre contas próprias, parcelamentos e regras de categoria seguem a [ADR 0018](../adr/0018-contas-periodos-transferencias-e-visoes.md). A biblioteca do usuário vive **no aparelho**, em arquivo cifrado (AES-256-GCM, chave no Keystore); o app a devolve à API ao abrir e a API a mantém só em memória ([ADR 0025](../adr/0025-armazenamento-no-aparelho-e-api-sem-estado.md)). O SQLite local da API, atrás de uma porta de repositório, segue como opção sem o app, e o backup criptografado `.trokim` leva os dados a outro aparelho ([ADR 0024](../adr/0024-persistencia-local-e-backup-criptografado.md)). O app só exibe o que o backend calculou. A categoria de cada gasto segue a ordem descrita em [Categorias](categorias.md): regras por palavra, dicionário de redes e atividade econômica (CNAE) pelo CNPJ do recebedor, com o índice local da [ADR 0020](../adr/0020-categorizacao-por-cnae.md). Os bancos SQLite (aplicação e base vetorial) usam SQLAlchemy e migrações numeradas do Alembic, aplicadas ao abrir cada banco ([ADR 0019](../adr/0019-orm-e-migracoes-numeradas.md)).

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuário (Android)
    participant Mobile as App Flutter
    participant API as Router FastAPI
    participant Parser as Parser Service
    participant Calc as Calculation Service
    participant Mem as Memória da API

    User->>Mobile: Escolhe banco, dono e tipo (ou pula) e um arquivo .ofx ou .pdf (seletor ou Compartilhar)
    Mobile->>API: POST /v1/transactions/inspect (sem gravar)
    API-->>Mobile: Banco, tipo, período, dono provável e avisos (arquivo no lugar errado)
    Mobile->>API: POST /v1/transactions/upload (multipart, dono e confirmação)
    API->>Parser: parse_ofx ou parse_pdf_text
    Parser->>Parser: Detecta o banco, classifica a natureza, limpa o estabelecimento e marca duplicatas (FITID)
    API->>API: Compara com os já importados (data, descrição, valor e tipo)
    API->>Mem: Guarda os lançamentos (duplicatas marcadas ficam fora dos totais)
    API->>API: Conta e período (substitui o mesmo período), transferências próprias e regras de categoria
    API-->>Mobile: filename, imported_count, institution, kind, outcome, statement, auto_transfers, transfer_suggestions
    Mobile->>API: GET /v1/transactions/summary
    API->>Calc: calculate_summary(lançamentos)
    Calc-->>API: Receitas, despesas, saldo, taxa de poupança e categorias
    API-->>Mobile: Resumo calculado pelo backend
    Mobile->>API: GET /v1/transactions
    API-->>Mobile: Lançamentos (o app agrupa por arquivo de origem)
    Mobile-->>User: Resumo e lista de arquivos atualizados
```

---

## 3. Fluxo de Pergunta Pedagógica via RAG Local

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuário (Android)
    participant Mobile as App Flutter
    participant API as Router FastAPI
    participant RAG as RAG Service
    participant Embed as FastEmbed
    participant VecDB as SQLite-Vec (vec0)
    participant Lexical as Índice TF-IDF

    User->>Mobile: "Como organizar minhas dívidas atrasadas?"
    Mobile->>API: POST /v1/chat/ask {"message": "..."}
    API->>RAG: answer_query(query)
    
    par Busca Vetorial Densa
        RAG->>Embed: Gera embedding da query (384d)
        Embed-->>RAG: Vetor normalizado
        RAG->>VecDB: Busca k vizinhos por proximidade de cosseno
        VecDB-->>RAG: Scores densos
    and Busca Léxica Esparsa
        RAG->>Lexical: Computa similaridade TF-IDF (palavras + n-grams)
        Lexical-->>RAG: Scores esparsos
    end
    
    RAG->>RAG: Combina scores: 0.3 * denso + 0.7 * esparso
    RAG->>RAG: Deduplica por documento e seleciona Top-3
    
    alt Score >= Limiar e Dentro do Escopo Educacional
        RAG-->>API: status: "grounded", resposta oficial + evidências tipadas
    else Score < Limiar ou Fora de Escopo (Especulação / Apostas)
        RAG-->>API: status: "abstained", mensagem de recusa ética
    end
    
    API-->>Mobile: JSON (ChatQueryResponse)
    Mobile-->>User: Exibe resposta formatada com cartões de fontes governamentais
```

---

## 4. Fluxo de Síntese Generativa Contextualizada (`POST /v1/chat/generate`)

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuário (Android)
    participant Mobile as App Flutter
    participant API as Router Chat
    participant Gen as Generation Service
    participant RAG as RAG Service
    participant Ollama as Provedor LLM (LiteLLM → Ollama local)

    User->>Mobile: Pergunta sobre conceito financeiro
    Mobile->>API: POST /v1/chat/generate {message, mode: "grounded"}
    API->>Gen: generate_answer(query, mode="grounded")
    
    alt Modo Grounded
        Gen->>RAG: retrieve_evidence(query)
        RAG-->>Gen: Evidências regulatórias
        alt Abstenção Ativa (Fora de escopo ou sem relevância)
            Gen-->>API: Resposta determinística de abstenção (sem chamar LLM)
        else Evidências Válidas Encontradas
            Gen->>Gen: Monta prompt versionado ancorado no contexto
            Gen->>Ollama: generate(prompt ancorado, temperatura 0,1)
            Ollama-->>Gen: Texto pedagógico sintetizado
            Gen-->>API: GenerateQueryResponse (answer + citations + evidences)
        end
    else Modo Pure (Zero-Shot)
        Gen->>Gen: Monta prompt pure sem contexto
        Gen->>Ollama: generate(prompt direto)
        Ollama-->>Gen: Texto gerado sem garantias regulatórias
        Gen-->>API: GenerateQueryResponse (answer, mode: "pure")
    else Modo Naive
        Gen->>RAG: Busca sem política estrita
        Gen->>Ollama: generate(prompt naive)
        Ollama-->>Gen: Texto gerado
        Gen-->>API: GenerateQueryResponse (answer, mode: "naive")
    end
    
    API-->>Mobile: Resposta JSON (ou 503 com mensagem clara se o modelo estiver indisponível)
    Mobile-->>User: Exibe síntese educacional com fontes clicáveis
```

---

## 5. Título da Conversa (`POST /v1/chat/title`)

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuário (Android)
    participant Mobile as App Flutter
    participant API as Router Chat
    participant Title as TitleService
    participant LLM as Provedor LLM (LiteLLM → Ollama local)

    User->>Mobile: Envia a primeira pergunta da conversa
    Mobile->>Mobile: Salva a conversa no aparelho com título provisório (pergunta encurtada)
    Mobile->>API: POST /v1/chat/title {message, answer?}
    API->>Title: Gera o título (prompt versionado, 3 a 6 palavras)
    alt Modelo responde a tempo
        Title->>LLM: generate(prompt de título)
        LLM-->>Title: Título curto
        Title-->>API: title, source = "llm"
    else Modelo indisponível, lento ou em modo mock
        Title-->>API: Primeiras palavras da pergunta, source = "fallback"
    end
    API-->>Mobile: Título
    Mobile-->>User: Atualiza o título (uma renomeação manual nunca é sobrescrita)
```

---

## 6. Fluxo Multiagente (`POST /v1/agents/ask`)

O sistema multiagente separa as responsabilidades entre agentes especializados com uma trilha de auditoria transparente:

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuário (Android)
    participant Mobile as App Flutter
    participant API as Router Agents (/v1/agents/ask)
    participant Orch as Orchestrator
    participant Research as Research Agent
    participant Analysis as Analysis Agent
    participant Comm as Communication Agent
    participant Val as Validation Agent

    User->>Mobile: Pergunta sobre finanças / gastos
    Mobile->>API: POST /v1/agents/ask {message}
    API->>Orch: run(question, transactions)
    
    rect rgb(240, 248, 255)
        note over Orch,Research: 1. Recuperação de evidências
        Orch->>Research: run(ctx)
        alt Fora de escopo ou sem evidência
            Research-->>Orch: StepStatus.ABSTAINED (abstain_reason)
            Orch-->>API: MultiAgentResponse (status: abstained, resposta fixa)
            API-->>Mobile: Resposta de abstenção + trilha
        else Evidências oficiais encontradas
            Research-->>Orch: StepStatus.OK (ctx.evidences)
        end
    end

    opt Pergunta requer cálculo (needs_analysis)
        rect rgb(255, 250, 240)
            note over Orch,Analysis: 2. Análise numérica determinística
            Orch->>Analysis: run(ctx)
            Analysis-->>Orch: StepStatus.OK (ctx.calculations, ctx.assumptions)
        end
    end

    rect rgb(245, 255, 245)
        note over Orch,Val: 3. Ciclo de Redação e Validação Defensiva
        loop Até max_revisions (padrão: 1)
            Orch->>Comm: run(ctx) (usa LLM)
            Comm-->>Orch: StepStatus.OK (ctx.draft_answer)
            Orch->>Val: run(ctx) (determinístico)
            alt Validação Aprovada
                Val-->>Orch: StepStatus.OK (sem blockers)
            else Blocker detectado e há revisão
                Val-->>Orch: StepStatus.FAILED (ctx.issues com BLOCKER)
                note over Orch,Comm: Reenvia ao Communication para correção
            else Blocker persistente ou sem revisão
                Val-->>Orch: StepStatus.FAILED
                Orch-->>API: MultiAgentResponse (status: rejected, resposta segura)
                API-->>Mobile: Rejeição segura + trilha de auditoria
            end
        end
    end

    Orch-->>API: MultiAgentResponse (status: answered, answer, steps, durações)
    API-->>Mobile: Resposta auditada com trilha dos agentes
    Mobile-->>User: Exibe resposta com botão "Como cheguei a essa resposta"
```


## Leitura de documento (componente da #88)

```mermaid
flowchart TD
    D["Arquivo em memória"] --> T{"Texto útil?"}
    T -->|Sim| P["Perfil textual"]
    T -->|Não| Q{"Qualidade da imagem"}
    Q -->|Insuficiente| A["Abstenção da página"]
    Q -->|Suficiente| O["OCR local"]
    P --> R["Campos para revisão"]
    O --> R
```

O [agente de documento](../agentes/document-agent.md) devolve campos e trilha sanitizada.
Visão opcional exige proteção dos pixels e política de confiança; permanece bloqueada
sem essas garantias. A extração chama a validação financeira (#89) em memória. A confirmação (#96) revalida os campos revisados, verifica duplicatas e grava a biblioteca no SQLite.
