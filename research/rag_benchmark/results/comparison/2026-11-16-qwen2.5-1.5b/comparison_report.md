# Relatório comparativo de respostas

Casos avaliados: **30**.

| Abordagem | F1 de tokens | Concept recall | Inconsistência factual | Abstention F1 | Latência média |
|---|---:|---:|---:|---:|---:|
| LLM pura | 11.0% | 48.9% | 83.3% | 0.0% | 3593 ms |
| RAG ingênuo | 16.3% | 80.6% | 56.7% | 0.0% | 3896 ms |
| Trokim estruturado | 17.2% | 75.0% | 44.8% | 50.0% | 3423 ms |

A taxa factual é uma heurística lexical, não uma prova semântica. Respostas sinalizadas exigem revisão humana.
