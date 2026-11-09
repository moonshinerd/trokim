# Ata 03 — Planejamento Operacional da Semana 3 (09/11/2026)

- **Data e Horário:** 09 de Novembro de 2026, 09h00 – 11h00  
- **Fase CBL:** Semana 3 — *Investigate & Act (Comparação LLM x RAG e Respostas Baseadas em Evidências)*  
- **Participantes:** Equipe Trokim (@moonshinerd, @Luix3005, @rebecaboncaputo, @gabrielcrzojo, @zainoca)  
- **Status da Sprint:** <span class="badge-should">Iniciada / Em Execução</span>

---

## 1. Pauta da Reunião

1. Análise da ementa e requisitos oficiais da **Semana 3** do Challenge 2 (Comparação LLM x RAG).
2. Estruturação do fluxo de trabalho sem ociosidade: garantia de tarefas independentes (não-bloqueantes) para todos os membros no primeiro dia da sprint.
3. Criação da Milestone 2 no GitHub com prazo de entrega até **Sexta-feira, 13/11/2026**.
4. Definição do protocolo de métricas de avaliação: Token-level F1 (SQuAD), cobertura de conceitos, taxa de alucinação e taxa de abstenção.
5. Arquitetura da camada de síntese generativa via port `LLMProvider` e suporte a Ollama local-first.

---

## 2. Deliberações e Distribuição de Responsabilidades

### 2.1 Estratégia de Não-Ociosidade (Fase 1 — Tarefas Não-Bloqueantes)
Para que todos os membros comecem a produzir imediatamente sem bloqueio mútuo, foram abertas 4 frentes simultâneas:

- **@gabrielcrzojo ([Issue #20](https://github.com/moonshinerd/trokim/issues/20)):** Curadoria do gabarito comparativo (30 perguntas) e redação dos 3 prompts versionados (`prompt_llm_pure_v1.txt`, `prompt_naive_rag_v1.txt` e `prompt_trokim_grounded_v1.txt`).
- **@rebecaboncaputo ([Issue #21](https://github.com/moonshinerd/trokim/issues/21)):** Implementação do framework de métricas em `research/rag_benchmark/eval_comparison.py`, cobrindo F1 de tokens, cobertura de conceitos, alucinação factual e abstenção ética.
- **@Luix3005 ([Issue #22](https://github.com/moonshinerd/trokim/issues/22)):** Desenvolvimento dos componentes visuais de auditoria e cartões de evidência governamentais no app Flutter.
- **@moonshinerd ([Issue #23](https://github.com/moonshinerd/trokim/issues/23)):** Criação do port abstrato `LLMProvider`, adaptadores (Ollama e Mock) e endpoint REST `POST /v1/chat/generate` na API FastAPI.

### 2.2 Fase 2 — Integração e Validação Empírica (Tarefas Bloqueantes)
Assim que os módulos da Fase 1 estiverem concluídos, as duplas realizam a integração:

- **@rebecaboncaputo e @moonshinerd ([Issue #24](https://github.com/moonshinerd/trokim/issues/24)):** Execução automatizada do benchmark comparativo entre as 3 abordagens (LLM pura, RAG ingênuo e Trokim estruturado).
- **@zainoca e @gabrielcrzojo ([Issue #25](https://github.com/moonshinerd/trokim/issues/25)):** Integração ponta a ponta do aplicativo Flutter ao backend com validação de usabilidade.
- **@moonshinerd e @gabrielcrzojo ([Issue #26](https://github.com/moonshinerd/trokim/issues/26)):** Formalização do relatório comparativo, elaboração da **ADR 0008** e publicação no MkDocs.

---

## 3. Metas de Qualidade para a Entrega 3 (13/11/2026)

1. **Demonstração de Redução de Alucinações:** A taxa de alucinação factual do Trokim estruturado deve ser expressivamente inferior à da LLM pura.
2. **Preservação da Abstenção Ética:** Manter 100% de recusa fundamentada em perguntas sobre apostas, day trade ou especulação.
3. **Privacidade Local-First:** Garantir que todo o fluxo continue executando localmente sem dependência de chaves de nuvem ou exposição de extratos à terceiros.
