# Mapa do Sistema

Visão visual das interações, componentes e fluxos de dados no **Trokim**.

---

## 1. Diagrama de Componentes C4 (Nível 2)

```mermaid
graph TD
    subgraph "Dispositivo Android (Mobile)"
        FlutterApp["App Flutter Trokim<br/>(UI Material 3 / Dart)"]
        StateManagement["Gerenciamento de Estado<br/>(Feature-First / Repositories)"]
        FlutterApp --> StateManagement
    end

    subgraph "Serviço Backend Local (Python / FastAPI)"
        APIEntry["Routers v1<br/>(/transactions, /chat, /budgets, /health)"]
        
        Parser["Parser de Documentos<br/>(OFX & PDF)"]
        CalcService["Motor de Cálculo Determinístico<br/>(Totais, Balanço, 50-30-20)"]
        RAGService["Mecanismo RAG Híbrido<br/>(Dense + Sparse TF-IDF)"]
        
        DomainCore["Entidades de Domínio Puro<br/>(Transaction, Budget, EvidenceChunk)"]
        
        subgraph "Persistência Local (SQLite)"
            DB[(SQLite Relacional<br/>Transações e Orçamentos)]
            VecDB[(SQLite-Vec<br/>Tabela Virtual vec0)]
        end
        
        APIEntry --> Parser
        APIEntry --> CalcService
        APIEntry --> RAGService
        
        Parser --> DomainCore
        CalcService --> DomainCore
        RAGService --> DomainCore
        
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
