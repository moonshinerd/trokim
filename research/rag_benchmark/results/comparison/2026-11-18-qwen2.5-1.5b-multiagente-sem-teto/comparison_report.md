# Relatório comparativo de respostas

Casos avaliados: **30**.

| Abordagem | F1 de tokens | Concept recall | Inconsistência factual | Abstention F1 | Latência média |
|---|---:|---:|---:|---:|---:|
| LLM pura | 14.3% | 45.0% | 43.3% | 0.0% | 3084 ms |
| RAG ingênuo | 19.6% | 68.3% | 43.3% | 0.0% | 2577 ms |
| Trokim estruturado | 21.0% | 70.0% | 31.0% | 50.0% | 1749 ms |
| Multiagente | 12.4% | 49.4% | 53.3% | 33.3% | 36570 ms |

A taxa factual é uma heurística lexical, não uma prova semântica. Respostas sinalizadas exigem revisão humana.
