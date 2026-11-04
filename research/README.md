# Trokim — Módulo de Pesquisa e RAG (Semana 2)

Laboratório de dados, documentos oficiais e benchmarks empíricos do projeto Trokim.

---

## Estrutura do Módulo

```text
research/
├── knowledge_base/           # Textos oficiais curados (BCB, CVM, CFPB)
│   ├── bcb_caderno_cidadania.txt
│   ├── cvm_planejamento_financeiro.txt
│   └── cfpb_financial_wellbeing.txt
├── synthetic_data/           # Geradores de extratos e faturas sintéticas (LGPD)
│   └── generate_datasets.py
└── rag_benchmark/            # Script de avaliação da Semana 2
    └── eval_rag.py
```

---

## Executando as Avaliações

```bash
# Executar o benchmark de recuperação e abstenção RAG
make rag-eval

# Gerar novas massas sintéticas de teste
make synthetic-data
```
