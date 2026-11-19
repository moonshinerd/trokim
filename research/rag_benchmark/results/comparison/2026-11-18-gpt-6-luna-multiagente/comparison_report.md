# Relatório comparativo de respostas

Casos avaliados: **30**.

| Abordagem | F1 de tokens | Concept recall | Inconsistência factual | Abstention F1 | Latência média |
|---|---:|---:|---:|---:|---:|
| LLM pura | 19.9% | 65.0% | 16.7% | 0.0% | 2888 ms |
| RAG ingênuo | 31.1% | 75.0% | 16.7% | 0.0% | 2014 ms |
| Trokim estruturado | 26.4% | 75.6% | 13.8% | 50.0% | 2550 ms |
| Multiagente | 11.7% | 88.3% | 35.7% | 80.0% | 3663 ms |

A taxa factual é uma heurística lexical, não uma prova semântica. Respostas sinalizadas exigem revisão humana.
