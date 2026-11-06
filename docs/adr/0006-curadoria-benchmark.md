# 0006 — Curadoria rastreável e benchmark de recuperação

- **Status:** Aceita
- **Data:** 06/11/2026
- **Requisitos / GQs:** RF05, RF06, RNF06; GQ05, GQ08, GQ11
- **Issue:** #4

## Contexto

O benchmark inicial aceitava qualquer evidência da mesma instituição e não interrompia
a execução ao falhar. Cabeçalhos entravam como evidência. Uma contagem de arquivos sem
verificação do conteúdo não garante uma base curada, e similaridade lexical sozinha não
é suficiente para decidir se o assistente pode atender um pedido.

## Decisão

Catalogar 20 fontes distintas com resumos editoriais, URLs e locais de conferência,
excertos curtos e hashes de proveniência. Extrair seções sem indexar cabeçalhos como
conteúdo. Manter citações de título e URL nas respostas extrativas.

Combinar TF-IDF de palavras e caracteres para tolerar flexões do português, mantendo
busca local, top-k=3 e limiar 0,15. Aplicar regras conservadoras de escopo antes da busca.
Essas regras não usam IDs nem textos exatos de perguntas do gabarito.

Avaliar por IDs de chunk e conceitos esperados, exigindo que a primeira evidência usada
na resposta seja pertinente. Separar recall@3, recuperação fundamentada e abstenção.
Falhar com código 1 ao ficar abaixo das metas e com código 2 para gabarito inválido.
Versionar resultados com hashes e preservar relatórios de CI mesmo em falha.

## Alternativas e consequências

Apenas contar instituição ou presença entre os três resultados pode aprovar respostas
cuja primeira evidência está errada. Exigir relevância da resposta evita esse falso acerto.
Gabaritos com conceitos são auditáveis e funcionam sem LLM julgadora, mas exigem revisão
humana e não avaliam qualidade de síntese generativa.

O controle sem política permite medir o efeito das regras de escopo. Não é uma comparação
com uma LLM sem fontes. Embeddings densos, persistência vetorial e síntese seguem nas
issues dependentes. Os casos usados para desenvolvimento não comprovam generalização;
novos conjuntos reservados serão necessários antes de conclusões mais amplas.
