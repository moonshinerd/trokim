#!/usr/bin/env bash
# Baixa os arquivos de Estabelecimentos e a tabela de CNAEs dos Dados Abertos do CNPJ (Receita
# Federal) para uma pasta fora do repositório. Uso: research/cnpj/baixar.sh 2026-11 [destino]
# Empresas e Sócios não são baixados: não são necessários e trazem nomes de pessoas.
set -euo pipefail
MES="${1:?informe o mês, ex.: 2026-11}"
DESTINO="${2:-$HOME/dados/receita-cnpj/$MES}"
BASE="https://arquivos.receitafederal.gov.br/public.php/dav/files/gn672Ad4CF8N6TK/Dados/Cadastros/CNPJ/$MES"
mkdir -p "$DESTINO"
cd "$DESTINO"
printf '%s\n' Cnaes.zip Estabelecimentos{0..9}.zip | xargs -P 5 -I{} \
  curl -sS -f -C - --retry 5 -o "{}" "$BASE/{}"
ls -la "$DESTINO"
