# Relatório comparativo de respostas

Casos avaliados: **30**.

| Abordagem | F1 de tokens | Concept recall | Inconsistência factual | Abstention F1 | Latência média |
|---|---:|---:|---:|---:|---:|
| LLM pura | 15.6% | 46.1% | 50.0% | 0.0% | 2942 ms |
| RAG ingênuo | 21.5% | 71.7% | 23.3% | 0.0% | 3149 ms |
| Trokim estruturado | 20.8% | 77.8% | 34.5% | 50.0% | 3203 ms |

A taxa factual é uma heurística lexical, não uma prova semântica. Respostas sinalizadas exigem revisão humana.

Para a auditoria qualitativa dos casos sinalizados, falsos positivos e limitações, consulte [comparison_audit.md](comparison_audit.md).
