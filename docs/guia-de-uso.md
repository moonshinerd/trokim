# Guia de Uso e Primeiros Passos

Instruções para configurar, executar e testar o ambiente de desenvolvimento do **Trokim**.

---

## 1. Pré-Requisitos

- **Python 3.12+** e gerenciador [uv](https://docs.astral.sh/uv/) instalado.
- **Flutter SDK (3.2.0+)** configurado para desenvolvimento Android.
- Navegador moderno ou cliente HTTP (como Insomnia, Postman ou curl).

---

## 2. Configuração do Backend e Dependências

Clone o repositório e execute a automação inicial:

```bash
# Cria api/.env e sincroniza o ambiente virtual uv
make setup

# Executa os testes automatizados para verificar a integridade
make test

# Inicia a API FastAPI localmente
make api-run
```

A API estará disponível em:
- **Endpoints e Swagger interativo:** `http://127.0.0.1:8000/docs`
- **Health check:** `http://127.0.0.1:8000/v1/health`

---

## 3. Execução da Documentação Local (MkDocs)

Para visualizar e editar a documentação viva em tempo real:

```bash
make docs-serve
```
Acesse no navegador: `http://127.0.0.1:8001`.

---

## 4. Executando o Módulo da Semana 2 (RAG & Sintéticos)

```bash
# Executa a avaliação empírica do motor RAG contra o gabarito
make rag-eval

# Gera novos extratos bancários sintéticos em formato OFX e PDF
make synthetic-data
```

---

## 5. Execução do Aplicativo Mobile (Flutter)

Com um emulador Android ou dispositivo físico conectado:

```bash
cd mobile
flutter run
```
