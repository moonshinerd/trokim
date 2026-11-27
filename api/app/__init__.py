"""API do Trokim."""

import os

# O LiteLLM baixa do GitHub, ao ser importado, a tabela de preços dos modelos.
# Num app local-first isso é uma saída de rede sem necessidade e, sem internet,
# atrasa a abertura com novas tentativas. A cópia que vem no pacote basta.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
