# Relatório comparativo de respostas

Casos avaliados: **30**.

| Abordagem | F1 de tokens | Concept recall | Inconsistência factual | Abstention F1 | Latência média |
|---|---:|---:|---:|---:|---:|
| LLM pura | 21.5% | 68.3% | 16.7% | 0.0% | 3126 ms |
| RAG ingênuo | 30.7% | 72.2% | 13.3% | 0.0% | 2120 ms |
| Trokim estruturado | 26.9% | 73.9% | 13.8% | 50.0% | 2992 ms |
| Multiagente | 11.3% | 89.4% | 39.3% | 80.0% | 4139 ms |

A taxa factual é uma heurística lexical, não uma prova semântica. Respostas sinalizadas exigem revisão humana.
