# Relatório comparativo de respostas

Casos avaliados: **30**.

| Abordagem | F1 de tokens | Concept recall | Inconsistência factual | Abstention F1 | Latência média |
|---|---:|---:|---:|---:|---:|
| LLM pura | 15.4% | 45.0% | 50.0% | 0.0% | 1926 ms |
| RAG ingênuo | 20.0% | 65.0% | 30.0% | 0.0% | 1806 ms |
| Trokim estruturado | 19.9% | 69.4% | 31.0% | 50.0% | 1721 ms |
| Multiagente | 11.8% | 72.8% | 43.5% | 40.0% | 2943 ms |

A taxa factual é uma heurística lexical, não uma prova semântica. Respostas sinalizadas exigem revisão humana.
