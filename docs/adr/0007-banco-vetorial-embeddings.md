# 0007 — Banco vetorial local e embeddings densos no RAG

- **Status:** Aceita
- **Data:** 07/11/2026
- **Requisitos / GQs:** RF05, RF06, RF10, RNF04; GQ05, GQ08, GQ10
- **Issue:** #8, #3

## Contexto

O recuperador da ADR 0006 indexa os documentos apenas com TF-IDF em memória.
A similaridade lexical falha em paráfrases e sinônimos comuns em português
("reserva de emergência" vs. "poupança para imprevistos"), o índice precisa ser
reconstruído a cada processo e cada resumo inteiro forma um único chunk, sem
granularidade para trechos relevantes dentro de documentos maiores. A issue #8
pede embeddings densos, persistência vetorial e pipeline de ingestão; a issue #3
expõe a consulta como endpoint tipado (`POST /v1/chat/ask`). Tudo precisa
continuar local-first (ADR 0002), sem chaves de API, e a resposta segue
extrativa: a síntese por LLM é o entregável de uma etapa posterior e o benchmark
compara a resposta byte a byte com o template extrativo.

## Decisão

Adotar ports abstratos em `api/app/models/` (`EmbeddingModel`, `VectorStore`) com
adaptadores em `api/app/clients/`, mantendo o domínio sem dependência de
infraestrutura.

Embeddings densos locais com `fastembed` (ONNX Runtime, sem chamada de rede nem
chave de API). Modelo padrão
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, multilíngue, com
384 dimensões e vetores normalizados, de modo que similaridade de cosseno se
reduz a produto interno.

Persistência vetorial com `sqlite-vec` (tabela virtual `vec0`) em arquivo SQLite
em `api/data/vector_store.db`, coerente com o SQLite embutido da ADR 0002. Uma
tabela de metadados guarda por chunk: `document_id`, fonte, URL, título, seção e
conteúdo.

Chunking por janela com sobreposição: quebra por frase, sem cortar palavras,
janelas de até `RAG_CHUNK_MAX_CHARS` caracteres e repetição, no início da janela
seguinte, das frases finais da anterior até `RAG_CHUNK_OVERLAP_TOKENS` palavras
(aproximação de token por palavra separada por espaço). Cabeçalhos de metadados
(`FONTE:`, `URL:`) nunca viram chunk. IDs no formato `<arquivo>_<n>` por
documento.

Busca híbrida: `score = alpha * cosseno_denso + (1 - alpha) * cosseno_tfidf`,
mantendo o TF-IDF de palavras e caracteres como componente lexical sobre os
mesmos chunks. `alpha` (`RAG_HYBRID_ALPHA`) e o limiar
(`RAG_SIMILARITY_THRESHOLD`) vêm de configuração e foram calibrados no benchmark
(tabela de calibração em `docs/rag/index.md`). No top-k, deduplicar por
documento: no máximo um chunk por `document_id`, o de maior score.

Cache e invalidação: o modelo de embeddings é cacheado por processo (fábrica com
`lru_cache`), e o banco persiste entre execuções. Metadados de índice guardam o
hash do corpus e o nome do modelo; na inicialização, reingere-se somente se o
banco estiver vazio, o hash do corpus divergir ou o modelo tiver mudado — caso
contrário o índice persistido é reutilizado sem recálculo.

A resposta de `answer_query` continua extrativa (trecho do primeiro chunk com
título e URL), sem LLM na geração, e as regras de escopo e abstenção da ADR 0006
permanecem inalteradas.

## Alternativas e consequências

**ChromaDB:** oferece índice aproximado e API de coleções pronta, mas adiciona
uma dependência pesada com servidor embutido e formato próprio de storage.
`sqlite-vec` entrega busca exata em arquivo único, reusa o SQLite já presente e
mantém o footprint local-first; o custo é implementar metadados e ingestão na
mão e abrir mão de índice aproximado — aceitável para uma base de dezenas de
chunks.

**Manter só TF-IDF:** zero dependências novas e já atende às metas de recall nos
casos conhecidos, mas não captura paráfrase nem oferece caminho de escala
semântica. A busca híbrida preserva esse componente lexical, de modo que
`alpha = 0` continua reproduzindo o comportamento anterior como fallback.

**Embeddings por API (OpenAI, OpenRouter etc.):** elimina o download do modelo
e o custo de inferência local, mas exige chave, rede e envio do conteúdo do
corpus a terceiro — contrário ao local-first e à LGPD da ADR 0002/RNF01 — além
de tornar testes e CI dependentes de serviço externo.

**Síntese por LLM (litellm/Ollama):** adiada de propósito. Manter a resposta
extrativa preserva a comparação byte a byte do benchmark e a rastreabilidade da
citação; a comparação LLM x RAG fica para a etapa dedicada.

Consequências operacionais: o modelo é baixado do Hugging Face na primeira
execução (cache em diretório fixo, também no CI); os testes usam embedder falso
e banco em `tmp_path` para não depender de rede nem tocar `api/data/`; a
relevância do gabarito passa a ser avaliada por `document_id`, com remapeamento
mecânico dos IDs de chunk. A calibração de `alpha` e do limiar é empírica e
registrada na documentação; se o componente denso não superar o lexical, a
configuração honesta é `alpha` baixo em vez de forçar embeddings.
