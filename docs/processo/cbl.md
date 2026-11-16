# Metodologia e Processo (CBL)

O desenvolvimento do Trokim adota a metodologia **Challenge Based Learning (CBL)** integrada a práticas ágeis e controle rigoroso de qualidade.

---

## Ciclos Semanais do CBL (7 Semanas)

1. **Engage (Engajamento):** Da Big Idea (*Qualidade de Vida*) à Essential Question (*"Como a IA pode ajudar no planejamento financeiro sem comprometer o bem-estar?"*).
2. **Investigate (Investigação):** Formulação e teste contínuo das 10 Perguntas Norteadoras (GQs), pesquisa documental em fontes oficiais e levantamento de hipóteses.
3. **Act (Ação):** Construção iterativa dos protótipos funcionais com entregas incrementais a cada semana:
   - Semana 1: Definição do problema, matriz de riscos e métricas.
   - Semana 2: Base regulada e primeiro motor RAG.
   - Semana 3: Comparativo LLM x RAG com métricas de fundamentação (concluída em 16/11/2026).
   - Semana 4: Orquestração multiagentes.
   - Semana 5: Agentes multimodais (visão em faturas/comprovantes).
   - Semana 6: Integração ponta a ponta (Flutter + Backend).
   - Semana 7: Validação final empírica e apresentação.

---

## Políticas de Engenharia e Rastreabilidade

- Cada decisão de design e escolha de tecnologia deve ser registrada como uma **ADR** em `docs/adr/`.
- Todos os requisitos (RF e RNF) rastreiam sua origem em uma ou mais Guiding Questions (GQ).
- Garantia de que a branch principal (`main`) permaneça sempre estável, exigindo validação de testes e documentação a cada entrega.
- **MkDocs sempre atualizado:** toda issue ou PR que muda comportamento, contrato de API, métrica, resultado ou arquitetura atualiza o MkDocs **no mesmo PR**: as páginas afetadas, a ADR (se houver decisão nova), os requisitos e a matriz de rastreabilidade, o planejamento e, quando houver resultados, o histórico de resultados e os gráficos (`make report-charts`). O `make docs-build` (modo estrito) precisa passar, e o PR não é mergeado com documentação defasada.
- **Revisão geral antes de cada semana:** no início de cada semana a equipe revisa todas as páginas do MkDocs contra o estado real do código e mergeia as correções antes de abrir as issues da semana.
