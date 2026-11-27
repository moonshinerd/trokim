"""A API não sai para a internet ao abrir (homologação da #100)."""

import os
import subprocess
import sys
from pathlib import Path


def test_litellm_usa_a_tabela_local():
    import app  # noqa: F401

    assert os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"


def test_importar_a_api_nao_abre_conexao_externa():
    script = """
import socket
tentativas = []
_connect = socket.socket.connect
def bloqueia(self, addr, *a):
    if isinstance(addr, tuple) and addr[0] not in ("127.0.0.1", "::1", "localhost"):
        tentativas.append(addr[0]); raise OSError("sem rede")
    return _connect(self, addr, *a)
socket.socket.connect = bloqueia
import app.main  # noqa: F401
import litellm  # noqa: F401
print("TENTATIVAS", tentativas)
"""
    env = {k: v for k, v in os.environ.items() if k != "LITELLM_LOCAL_MODEL_COST_MAP"}
    out = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert "TENTATIVAS []" in out.stdout, out.stdout[-2000:]
