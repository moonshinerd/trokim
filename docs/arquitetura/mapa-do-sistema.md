# Mapa do Sistema

Visão visual das interações, componentes e fluxos de dados no **Trokim**.

---

## 1. Diagrama de Componentes C4 (Nível 2)

```mermaid
graph TD
    subgraph "Dispositivo Android (Mobile)"
        FlutterApp["App Flutter Trokim<br/>(UI Material 3 / Dart)"]
        StateManagement["Gerenciamento de Estado<br/>(Bloc / Provider)"]
        FlutterApp --> StateManagement
    end

    subgraph "Serviço Backend Local (Python / FastAPI)"
        APIEntry["Routers v1<br/>(Transactions, Chat, Budgets)"]
        
        Parser["Parser de Documentos<br/>(OFX & PDF)"]
        CalcService["Motor de Cálculo Determinístico<br/>(Totais, Médias, Balanço)"]
        RAGService["Mecanismo RAG<br/>(Busca e Abstenção)"]
        
        DomainCore["Entidades de Domínio Puro<br/>(Transaction, Budget, Evidence)"]
        DB[(SQLite Local)]
        
        APIEntry --> Parser
        APIEntry --> CalcService
        APIEntry --> RAGService
        
        Parser --> DomainCore
        CalcService --> DomainCore
        RAGService --> DomainCore
        
        DomainCore --> DB
    end

    subgraph "Base de Conhecimento e Modelos"
        KnowledgeBase["Documentos Curados<br/>(BCB, CVM, CFPB)"]
        LLM["Modelo de Linguagem<br/>(Explicação e Diálogo)"]
        
        RAGService --> KnowledgeBase
        RAGService --> LLM
    end

    StateManagement -->|HTTP / JSON| APIEntry
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
    Parser->>Parser: Extrai transações e remove duplicatas
    Parser->>DB: Salva novos lançamentos
    API->>Calc: compute_balance_and_metrics()
    Calc->>DB: Consulta lançamentos consolidados
    Calc-->>API: Totais, despesas por categoria, saldo
    API-->>Mobile: Retorno JSON formatado
    Mobile-->>User: Exibe Dashboard financeiro atualizado
```

---

## 3. Fluxo de Pergunta Pedagógica via RAG (Semana 2)

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuário (Android)
    participant Mobile as App Flutter
    participant API as Router FastAPI
    participant RAG as RAG Service
    participant Docs as Base Oficial (BCB/CVM)
    participant LLM as Modelo de Linguagem

    User->>Mobile: "Como montar uma reserva de emergência?"
    Mobile->>API: POST /v1/chat/ask
    API->>RAG: answer_financial_query(question)
    RAG->>Docs: Busca trechos relevantes (Top-K)
    alt Evidências encontradas (Score >= limiar)
        RAG->>LLM: Injeta prompt com citações obrigatórias
        LLM-->>RAG: Resposta fundamentada com referência
    else Nenhuma evidência relevante (Score < limiar)
        RAG-->>API: Declaração de abstenção com base nas regras
    end
    API-->>Mobile: Resposta + Fontes citadas
    Mobile-->>User: Exibe mensagem na interface de chat
```
