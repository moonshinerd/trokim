# Relatório comparativo de respostas

Casos avaliados: **30**.

| Abordagem | F1 de tokens | Concept recall | Inconsistência factual | Abstention F1 | Latência média |
|---|---:|---:|---:|---:|---:|
| LLM pura | 14.0% | 46.7% | 53.3% | 0.0% | 1969 ms |
| RAG ingênuo | 20.0% | 67.8% | 30.0% | 0.0% | 1684 ms |
| Trokim estruturado | 18.5% | 69.4% | 34.5% | 50.0% | 1512 ms |
| Multiagente | 12.1% | 62.8% | 45.0% | 30.8% | 3522 ms |

A taxa factual é uma heurística lexical, não uma prova semântica. Respostas sinalizadas exigem revisão humana.
