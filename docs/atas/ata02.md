# Ata 02 — Checkpoint e Consolidação da Semana 2 (06/11/2026)

- **Data e Horário:** 06 de Novembro de 2026, 15h00 – 17h00  
- **Fase CBL:** Semana 2 — *Investigate & Act (Base de Conhecimento e Recuperação)*  
- **Participantes:** Equipe Trokim (@moonshinerd, @Luix3005, @rebecaboncaputo, @gabrielcrzojo)  
- **Status do Entregável:** <span class="badge-must">Concluído e Auditado</span>

---

## 1. Pauta da Reunião

1. Validação final dos 20 documentos oficiais curados e catalogados em `research/knowledge_base/`.
2. Avaliação dos resultados empíricos do benchmark RAG (Recall@3, precisão, taxa de abstenção e calibração do $\alpha$).
3. Homologação da integração do endpoint `POST /v1/chat/ask` com a interface mobile em Flutter.
4. Verificação da massa sintética de dados (OFX e PDF) em conformidade com a LGPD.
5. Transição e planejamento da Semana 3 (Comparação LLM pura vs. RAG fundamentado).

---

## 2. Deliberações e Decisões Técnicas

### 2.1 Base de Conhecimento Oficial (ADR 0006)
- Confirmada a inclusão dos 20 documentos institucionais, organizados em 4 órgãos oficiais:
  - **Banco Central do Brasil (BCB):** 5 cadernos e cartilhas cobrindo orçamento, crédito, dívidas, CET e regras do rotativo.
  - **Comissão de Valores Mobiliários (CVM):** 7 documentos sobre reserva de emergência, objetivos, suitability, liquidez e relação risco x retorno.
  - **Consumer Financial Protection Bureau (CFPB):** 5 documentos sobre mensuração de bem-estar financeiro e riscos de chatbots.
  - **Autoridade Nacional de Proteção de Dados (ANPD):** 3 guias sobre princípios de minimização, retenção e segurança da informação.
- Todos os arquivos possuem hashes SHA-256 e URLs canônicas catalogadas em `research/knowledge_base/catalog.json`.

### 2.2 Motor de Recuperação Vetorial e Híbrida (ADR 0007)
- Adotado o modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões) via FastEmbed local.
- Persistência vetorial em SQLite com a extensão `sqlite-vec` (tabela virtual `vec0`), garantindo processamento *local-first* sem servidores externos.
- Calibração do índice híbrido fixada em $\alpha = 0,3$ (ponderação entre cosseno denso e TF-IDF léxico), atingindo:
  - **Recall@3:** 98,78% (40/41 consultas de teste atendidas no top-3).
  - **Recuperação Fundamentada:** 95,12%.
  - **Taxa de Abstenção Ativa:** 100% (20/20 casos fora de escopo corretamente recusados).
  - **Latência média:** ~12,4 ms por consulta na CPU.

### 2.3 Interface Mobile (Flutter Android)
- Concluída a implementação do chat conversacional no Flutter integrado ao endpoint local `/v1/chat/ask`.
- Exibição de cartões de evidência destacando a fonte oficial citada (BCB, CVM, CFPB), score de relevância e link original.
- Tratamento explícito para respostas com status `abstained`, informando o usuário com transparência.

### 2.4 Conformidade com a LGPD e Massa Sintética
- Homologado o gerador em `research/synthetic_data/`, produzindo extratos bancários `.ofx` e faturas `.pdf` sintéticas e reproduzíveis.
- Nenhuma informação financeira real de membros da equipe ou terceiros foi ou será commitada no repositório.

---

## 3. Próximos Passos (Semana 3)

1. Estruturar o protocolo de avaliação para comparar:
   - LLM pura (sem fontes).
   - LLM com RAG ingênuo (sem controle de escopo).
   - LLM com RAG estruturado do Trokim (híbrido + abstenção + cálculo determinístico).
2. Criar os prompts da Semana 3 em `api/app/prompts/` com métricas de alucinação e conformidade factual.
3. Iniciar a classificação determinística de despesas na regra orçamentária 50-30-20.
