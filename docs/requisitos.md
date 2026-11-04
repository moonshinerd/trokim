# Requisitos do Sistema e Rastreabilidade

Rastreabilidade bidirecional entre Requisitos Funcionais (RF), Requisitos Não Funcionais (RNF), priorização MoSCoW e Guiding Questions (GQ).

---

## Requisitos Funcionais (RF)

| ID | Requisito Funcional | Descrição | Priorização (MoSCoW) | Origem | ADR Relacionada |
|---|---|---|---|---|---|
| **RF01** | Importação de extratos OFX | O sistema deve ler e extrair transações financeiras de arquivos padronizados `.ofx`. | <span class="badge-must">Must have</span> | GQ02, GQ03 | ADR 0005 |
| **RF02** | Importação de faturas PDF | O sistema deve extrair texto e transações de faturas bancárias em formato `.pdf`. | <span class="badge-must">Must have</span> | GQ02, GQ03 | ADR 0005 |
| **RF03** | Cálculo determinístico de totais | O sistema deve calcular receitas, despesas, saldos e totais por categoria sem uso de LLM. | <span class="badge-must">Must have</span> | GQ04 | ADR 0004 |
| **RF04** | Deduplicação de transações | O sistema deve identificar transações idênticas importadas repetidamente pelo usuário. | <span class="badge-must">Must have</span> | GQ02, GQ04 | ADR 0004 |
| **RF05** | Consulta pedagógica via RAG | O usuário pode fazer perguntas em linguagem natural respondidas com base nas publicações do BCB, CVM e CFPB. | <span class="badge-must">Must have</span> | GQ01, GQ05 | ADR 0003 |
| **RF06** | Abstenção orientada a evidências | O sistema deve declarar explicitamente que não possui informações quando a pergunta estiver fora do material de apoio. | <span class="badge-must">Must have</span> | GQ05 | ADR 0003 |
| **RF07** | Dashboard consolidado no Android | O aplicativo móvel deve exibir o resumo financeiro, saldo atual e gráficos simplificados. | <span class="badge-must">Must have</span> | GQ07 | ADR 0001 |
| **RF08** | Simulação de cenários de orçamento | O sistema deve permitir comparar dois cenários orçamentários (ex.: corte de despesas vs. meta de economia). | <span class="badge-should">Should have</span> | GQ01, GQ06 | ADR 0004 |
| **RF09** | Categorização automática assistida | O sistema deve sugerir categorias para lançamentos com base no histórico do usuário. | <span class="badge-should">Should have</span> | GQ01, GQ04 | ADR 0004 |
| **RF10** | Auditoria e citação de fontes | Cada orientação financeira gerada deve apontar o trecho e o órgão regulador de onde a recomendação se originou. | <span class="badge-must">Must have</span> | GQ08 | ADR 0003 |

---

## Requisitos Não Funcionais (RNF)

| ID | Requisito Não Funcional | Descrição | Priorização (MoSCoW) | Origem | ADR Relacionada |
|---|---|---|---|---|---|
| **RNF01** | Privacidade e Conformidade LGPD | Nenhum extrato bancário ou dado sensível deve ser persistido em servidores de terceiros. | <span class="badge-must">Must have</span> | GQ03 | ADR 0002, ADR 0005 |
| **RNF02** | Explicabilidade e Acurácia Numérica | Cálculos financeiros devem ter 100% de precisão matemática e código coberto por testes. | <span class="badge-must">Must have</span> | GQ04 | ADR 0004 |
| **RNF03** | Portabilidade e Eficiência Mobile | O app Android deve ser responsivo, consumindo poucos recursos através do Flutter. | <span class="badge-must">Must have</span> | GQ07 | ADR 0001 |
| **RNF04** | Latência de Resposta RAG | As consultas RAG devem responder em menos de 3 segundos em ambiente de desenvolvimento local. | <span class="badge-should">Should have</span> | GQ05 | ADR 0002, ADR 0003 |
| **RNF05** | Separação Limpa de Camadas | O backend deve isolar o domínio das rotas e adaptadores (`routers -> services -> domain`). | <span class="badge-must">Must have</span> | GQ10 | ADR 0002 |
| **RNF06** | Testabilidade com Dados Sintéticos | Toda a suíte de testes deve rodar sem conexão bancária real ou dados de usuários vivos. | <span class="badge-must">Must have</span> | GQ03, GQ09 | ADR 0005 |
