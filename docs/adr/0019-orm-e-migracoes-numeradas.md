# 0019 — ORM (SQLAlchemy) e migrações numeradas (Alembic) nos bancos SQLite

- **Status:** Aceita
- **Data:** 18/11/2026
- **Requisitos / GQs:** RF12, RNF01, RNF05, RNF07; GQ03, GQ06
- **ADRs relacionadas:** [0002](0002-fastapi-sqlite-local.md), [0007](0007-banco-vetorial-embeddings.md), [0015](0015-dados-reais-importacao-e-endereco-da-api.md)

## Contexto

A API tinha dois bancos SQLite, cada um criado de um jeito:

- o **banco da aplicação** (`DATABASE_URL`, `trokim.db`) já usava SQLAlchemy, mas criava as
  tabelas com `Base.metadata.create_all` na subida da API. Não havia versão gravada: uma coluna
  nova não chegaria aos bancos existentes;
- a **base vetorial do RAG** (`data/vector_store.db`, [ADR 0007](0007-banco-vetorial-embeddings.md))
  usava SQL escrito à mão (`CREATE TABLE IF NOT EXISTS`, `INSERT`, `SELECT`) direto no adaptador.

Com a persistência dos lançamentos chegando ([ADR 0015](0015-dados-reais-importacao-e-endereco-da-api.md)),
o esquema vai mudar com frequência. Sem migrações numeradas, cada mudança dependeria de apagar o
banco do usuário.

## Decisão

1. **ORM:** os dois bancos usam **SQLAlchemy 2** com modelos declarativos
   (`app/db/database.py` e `app/db/vector_models.py`). Leitura e escrita passam pelo ORM.
2. **Migrações:** o esquema vem só do **Alembic**, uma pasta por banco
   (`api/migrations/app` e `api/migrations/vetorial`), com revisões numeradas em sequência:
   `001_esquema_inicial.py`, `002_...`. O número é o próprio id da revisão
   (`--rev-id 002`) e o `down_revision` aponta para o número anterior.
3. **Aplicação automática:** a API aplica as revisões pendentes ao abrir cada banco
   (`app.db.migrate.upgrade`): o banco da aplicação na subida (`init_db`) e a base vetorial ao
   criar o `SQLiteVectorStore`. `create_all` não é mais usado.
4. **Adoção dos bancos antigos:** a revisão `001` cria tabelas e índices com `if_not_exists`;
   bancos criados antes desta ADR são adotados como `001` sem perder dados.
5. **Exceção do sqlite-vec:** a tabela virtual `vec_chunks` (`vec0`) e a busca com `MATCH` não
   têm representação no ORM. A tabela é criada na migração com DDL e a busca usa `text()` do
   SQLAlchemy, isolada em `SQLiteVectorStore`. Trocar o modelo de embeddings (outra dimensão)
   recria o índice, porque os vetores derivam dos documentos.
6. **Regra de manutenção:** revisão publicada não se edita; mudança de esquema entra como a
   próxima revisão. O teste `api/tests/test_migrations.py` falha se a numeração tiver buraco,
   repetição ou nome fora do padrão `NNN_descricao.py`.

Para criar uma revisão nova, na pasta `api/`:

```bash
uv run alembic -n app revision --autogenerate -m "descricao" --rev-id 002
uv run alembic -n vetorial revision -m "descricao" --rev-id 002
```

## Alternativas consideradas

- **Manter `create_all` e SQL à mão.** Descartada: não há como evoluir o esquema dos bancos já
  criados sem apagar dados.
- **Migrações em arquivos `.sql` com `PRAGMA user_version`.** Mais simples, mas duplica o esquema
  (modelo ORM e SQL) e não gera revisões a partir dos modelos.
- **SQLModel.** Acrescenta uma camada sobre o SQLAlchemy sem ganho para dois bancos pequenos.

## Consequências

- Mudança de esquema vira revisão revisável no PR, com teste de sequência.
- A dependência `alembic` entra na API; `sqlalchemy` já estava.
- A busca vetorial continua com um trecho de SQL textual, documentado como exceção.
