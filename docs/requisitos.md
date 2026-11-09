# Requisitos do Sistema e Matriz de Rastreabilidade

Rastreabilidade bidirecional entre os Requisitos do Sistema (Funcionais e Não Funcionais), priorização MoSCoW, as Perguntas Norteadoras da Pesquisa (GQ01 a GQ13) e as Decisões de Arquitetura (ADRs).

---

## Técnica de Levantamento e Priorização de Requisitos

O processo de engenharia de requisitos do **Trokim** seguiu uma abordagem orientada a objetivos, estruturada em duas frentes complementares:

1. **Formulação de Guiding Questions (GQ01 a GQ13):** Essenciais para a compreensão do problema central da fragmentação financeira. Cada necessidade de negócio e restrição de segurança foi decomposta em requisitos funcionais (RF) e não funcionais (RNF). A coluna de **Origem** estabelece uma rastreabilidade bidirecional direta: todo requisito implementado é formalmente justificado por uma ou mais Guiding Questions, prevenindo requisitos órfãos e desvios de escopo (*scope creep*).
2. **Priorização MoSCoW:** Utilizada para gerenciar o escopo do MVP no curto ciclo de 7 semanas do CBL:
    - <span class="badge-must">Must have</span>: Itens críticos para o fluxo de valor do MVP (importação de OFX/PDF, cálculo determinístico sem alucinação, RAG oficial com abstenção ativa, interface mobile Flutter e privacidade local-first).
    - <span class="badge-should">Should have</span>: Recursos fundamentais que aumentam a eficácia e usabilidade (comparação de dois cenários de orçamento, categorização automática assistida e deduplicação de faturas).
    - <span class="badge-could">Could have</span>: Recursos de valor agregado para iterações seguintes (projeções estatísticas de séries temporais e categorização multimodal via visão computacional na Semana 5).
    - **Won't have**: Integração bancária direta via Open Finance com agregação comercial de terceiros no MVP (descartada pela [ADR 0005](adr/0005-importacao-local-ofx-pdf.md)).

---

## Requisitos Funcionais (RF)

| ID | Requisito Funcional | Descrição | Priorização (MoSCoW) | Origem | ADR Relacionada |
|---|---|---|---|---|---|
| **RF01** | Importação de extratos OFX | O sistema deve ler e extrair lançamentos de extratos bancários em formato `.ofx`. | <span class="badge-must">Must have</span> | [GQ02](pesquisa/guiding-questions.md), [GQ03](pesquisa/guiding-questions.md) | [ADR 0005](adr/0005-importacao-local-ofx-pdf.md) |
| **RF02** | Importação de faturas PDF | O sistema deve extrair texto e transações de faturas de cartão de crédito em formato `.pdf`. | <span class="badge-must">Must have</span> | [GQ02](pesquisa/guiding-questions.md), [GQ03](pesquisa/guiding-questions.md) | [ADR 0005](adr/0005-importacao-local-ofx-pdf.md) |
| **RF03** | Cálculo determinístico de totais | O sistema deve calcular saldos, receitas, despesas e percentual de poupança exclusivamente por código matemático em Python, sem intervenção aritmética de LLMs. | <span class="badge-must">Must have</span> | [GQ04](pesquisa/guiding-questions.md), [GQ07](pesquisa/guiding-questions.md) | [ADR 0004](adr/0004-calculos-deterministicos.md) |
| **RF04** | Deduplicação de transações | O sistema deve identificar e sinalizar automaticamente transações repetidas entre extratos bancários e faturas de cartão. | <span class="badge-must">Must have</span> | [GQ02](pesquisa/guiding-questions.md), [GQ07](pesquisa/guiding-questions.md) | [ADR 0004](adr/0004-calculos-deterministicos.md) |
| **RF05** | Consulta pedagógica via RAG | O usuário pode enviar perguntas em linguagem natural respondidas com base nas publicações oficiais do BCB, CVM e CFPB. | <span class="badge-must">Must have</span> | [GQ01](pesquisa/guiding-questions.md), [GQ05](pesquisa/guiding-questions.md), [GQ10](pesquisa/guiding-questions.md) | [ADR 0003](adr/0003-rag-fontes-oficiais.md), [ADR 0006](adr/0006-curadoria-benchmark.md), [ADR 0007](adr/0007-banco-vetorial-embeddings.md) |
| **RF06** | Abstenção ativa de IA | O sistema deve recusar responder formalmente quando uma pergunta do usuário estiver fora do escopo ou não tiver respaldo oficial comprovado. | <span class="badge-must">Must have</span> | [GQ05](pesquisa/guiding-questions.md), [GQ10](pesquisa/guiding-questions.md) | [ADR 0003](adr/0003-rag-fontes-oficiais.md), [ADR 0006](adr/0006-curadoria-benchmark.md) |
| **RF07** | Dashboard consolidado no Android | O aplicativo móvel deve exibir o resumo financeiro, saldo líquido, métricas de poupança e distribuição por categoria. | <span class="badge-must">Must have</span> | [GQ01](pesquisa/guiding-questions.md), [GQ07](pesquisa/guiding-questions.md), [GQ13](pesquisa/guiding-questions.md) | [ADR 0001](adr/0001-flutter-android.md) |
| **RF08** | Simulação e comparação de cenários | O sistema deve permitir comparar dois cenários orçamentários (ex.: Cenário Padrão vs. Otimizado com meta de reserva de emergência). | <span class="badge-should">Should have</span> | [GQ06](pesquisa/guiding-questions.md), [GQ08](pesquisa/guiding-questions.md), [GQ12](pesquisa/guiding-questions.md) | [ADR 0004](adr/0004-calculos-deterministicos.md) |
| **RF09** | Categorização automática assistida | O sistema deve inferir a categoria das transações com base no histórico do usuário, permitindo conferência e ajuste no app. | <span class="badge-should">Should have</span> | [GQ07](pesquisa/guiding-questions.md), [GQ11](pesquisa/guiding-questions.md) | [ADR 0004](adr/0004-calculos-deterministicos.md) |
| **RF10** | Auditoria e citação direta de fontes | Cada orientação gerada pelo assistente deve referenciar explicitamente o órgão oficial (ex.: Banco Central) e a seção documental correspondente. | <span class="badge-must">Must have</span> | [GQ05](pesquisa/guiding-questions.md), [GQ08](pesquisa/guiding-questions.md) | [ADR 0003](adr/0003-rag-fontes-oficiais.md), [ADR 0006](adr/0006-curadoria-benchmark.md), [ADR 0007](adr/0007-banco-vetorial-embeddings.md) |

---

## Requisitos Não Funcionais (RNF)

| ID | Requisito Não Funcional | Descrição | Priorização (MoSCoW) | Origem | ADR Relacionada |
|---|---|---|---|---|---|
| **RNF01** | Privacidade Local-First (LGPD) | Os extratos bancários e transações devem ser armazenados localmente no dispositivo/servidor local em SQLite, sem persistência em servidores de terceiros. | <span class="badge-must">Must have</span> | [GQ03](pesquisa/guiding-questions.md), [GQ06](pesquisa/guiding-questions.md) | [ADR 0002](adr/0002-fastapi-sqlite-local.md), [ADR 0005](adr/0005-importacao-local-ofx-pdf.md) |
| **RNF02** | Explicabilidade e Acurácia Aritmética | O motor de cálculo determinístico deve possuir 100% de acurácia numérica e cobertura por testes automatizados com `pytest`. | <span class="badge-must">Must have</span> | [GQ04](pesquisa/guiding-questions.md), [GQ11](pesquisa/guiding-questions.md) | [ADR 0004](adr/0004-calculos-deterministicos.md) |
| **RNF03** | Portabilidade e Performance Mobile | A interface do app Android deve manter taxa estável de quadros e baixo consumo de memória através da compilação em Flutter. | <span class="badge-must">Must have</span> | [GQ01](pesquisa/guiding-questions.md) | [ADR 0001](adr/0001-flutter-android.md) |
| **RNF04** | Latência na Recuperação RAG | As consultas RAG locais devem recuperar as evidências e responder em menos de 2 segundos em ambiente de desenvolvimento local. | <span class="badge-should">Should have</span> | [GQ05](pesquisa/guiding-questions.md), [GQ10](pesquisa/guiding-questions.md) | [ADR 0003](adr/0003-rag-fontes-oficiais.md), [ADR 0007](adr/0007-banco-vetorial-embeddings.md) |
| **RNF05** | Arquitetura Limpa em Camadas | O backend deve isolar estritamente o domínio das rotas e adaptadores (`routers → services → domain`), prevenindo acoplamento indevido. | <span class="badge-must">Must have</span> | [GQ03](pesquisa/guiding-questions.md) | [ADR 0002](adr/0002-fastapi-sqlite-local.md) |
| **RNF06** | Testabilidade com Dados Sintéticos | Toda a suíte de testes e validação de hipóteses deve rodar com dados sintéticos em `research/synthetic_data/`, sem uso de dados reais de alunos. | <span class="badge-must">Must have</span> | [GQ02](pesquisa/guiding-questions.md), [GQ03](pesquisa/guiding-questions.md), [GQ04](pesquisa/guiding-questions.md) | [ADR 0005](adr/0005-importacao-local-ofx-pdf.md), [ADR 0006](adr/0006-curadoria-benchmark.md) |
