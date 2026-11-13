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
        FlutterApp --> StateManagement
        FlutterApp --> DesignSystem
        FlutterApp --> Settings
    end

    subgraph "Serviço Backend Local (Python / FastAPI)"
        APIEntry["Routers v1<br/>(/transactions, /chat, /budgets, /health)"]
        
        Parser["Parser de Documentos<br/>(OFX & PDF)"]
        CalcService["Motor de Cálculo Determinístico<br/>(Totais, Balanço, 50-30-20)"]
        RAGService["Mecanismo RAG Híbrido<br/>(Dense + Sparse TF-IDF)"]
        GenService["Serviço de Síntese Generativa<br/>(GenerationService)"]
        
        DomainCore["Entidades de Domínio Puro<br/>(Transaction, Budget, EvidenceChunk)"]
        
        subgraph "Persistência Local (SQLite)"
            DB[(SQLite Relacional<br/>Transações e Orçamentos)]
            VecDB[(SQLite-Vec<br/>Tabela Virtual vec0)]
        end

        subgraph "Provedores de Inferência Local (LLM)"
            OllamaClient["OllamaProvider<br/>(Qwen 2.5 Local)"]
            MockLLM["MockLLMProvider<br/>(Testes & CI)"]
        end
        
        APIEntry --> Parser
        APIEntry --> CalcService
        APIEntry --> RAGService
        APIEntry --> GenService
        
        Parser --> DomainCore
        CalcService --> DomainCore
        RAGService --> DomainCore
        GenService --> RAGService
        GenService --> OllamaClient
        GenService --> MockLLM
        
        DomainCore --> DB
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

## 2. Fluxo de Importação e Cálculo de Extratos

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuário (Android)
    participant Mobile as App Flutter
    participant API as Router FastAPI
    participant Parser as Parser Service
    participant Calc as Calculation Service
    participant DB as SQLite Local

    User->>Mobile: Seleciona arquivo .ofx ou .pdf
    Mobile->>API: POST /v1/transactions/upload
    API->>Parser: parse_file(content, filename)
    Parser->>Parser: Extrai transações e valida duplicatas
    Parser->>DB: Salva lançamentos normalizados
    API->>Calc: compute_balance_and_metrics()
    Calc->>DB: Consulta lançamentos consolidados
    Calc-->>API: Totais, saldo, despesas essenciais e estilo de vida
    API-->>Mobile: Retorno JSON com dados determinísticos
    Mobile-->>User: Exibe Dashboard financeiro atualizado (0% erro)
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
    participant Ollama as Ollama / Qwen 2.5 Local

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
            Gen->>Ollama: POST /api/generate (prompt ancorado, temp=0.1)
            Ollama-->>Gen: Texto pedagógico sintetizado
            Gen-->>API: GenerateQueryResponse (answer + citations + evidences)
        end
    else Modo Pure (Zero-Shot)
        Gen->>Gen: Monta prompt pure sem contexto
        Gen->>Ollama: POST /api/generate (prompt direto)
        Ollama-->>Gen: Texto gerado sem garantias regulatórias
        Gen-->>API: GenerateQueryResponse (answer, mode: "pure")
    else Modo Naive
        Gen->>RAG: Busca sem política estrita
        Gen->>Ollama: POST /api/generate (prompt naive)
        Ollama-->>Gen: Texto gerado
        Gen-->>API: GenerateQueryResponse (answer, mode: "naive")
    end
    
    API-->>Mobile: Resposta JSON
    Mobile-->>User: Exibe síntese educacional enriquecida
```
