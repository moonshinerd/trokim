# Arquitetura do Sistema

A arquitetura do **Trokim** foi concebida para atender aos requisitos de alta performance de geração por inteligência artificial, estrita observância à LGPD (*privacy by design*) e facilidade de integração contínua.

---

## Decisões Estruturais Principais

1. **Camada Mobile (Android / Flutter):**
   - Desenvolvida em Dart/Flutter, garantindo um código fortemente tipado, padrões de componentes limpos e compilação direta para Android.
   - O aplicativo atua como o cliente primário, fornecendo telas de dashboard, assistente conversacional, gerenciador de lançamentos e seletor de arquivos de extrato.
2. **Camada Backend (FastAPI / Python 3.12+):**
   - FastAPI pela velocidade de execução, suporte a async nativo e rica integração com bibliotecas de processamento de texto e dados (OFX, PDF, scikit-learn).
   - Gerenciamento de pacotes ultra-rápido com `uv`.
   - Banco de dados embutido **SQLite** garantindo que a aplicação funcione completamente local sem containers ou servidores adicionais de banco.
3. **Mecanismo RAG (Semana 2):**
   - Camada de recuperação vetorial e semântica sobre os documentos oficiais curados em `research/knowledge_base/`.
   - Prompts versionados em `api/app/prompts/` com instrução estrita de citação e abstenção.

---

## Camadas do Backend (`api/`)

O backend herda a separação limpa adotada no projeto ContrarIA:

```text
routers/ (HTTP fino, validação de requisições e respostas Pydantic)
   │
   ▼
services/ (Regras de negócio, cálculos matemáticos, orquestração de RAG)
   │
   ▼
domain/   (Entidades puras independentes de frameworks: Transaction, Budget, Evidence)
   ▲
   │
clients/  (Adaptadores de persistência SQLite, leitores de arquivos e provedores de IA)
```

Essa estrutura garante que a evolução do sistema nas semanas 4 (Multiagentes) e 5 (Multimodalidade) ocorra sem acoplamento indevido.
