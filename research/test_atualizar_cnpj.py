"""Atualizador do índice CNPJ, sem rede: aviso, confirmação e o que ele apaga."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/cnpj"))
SPEC = importlib.util.spec_from_file_location("atualizar", ROOT / "research/cnpj/atualizar.py")
atualizar = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(atualizar)


def _sem_rede(monkeypatch, mes="2099-01"):
    tamanhos = {nome: 1000 for nome in atualizar.ARQUIVOS}
    monkeypatch.setattr(atualizar, "mes_mais_recente", lambda: mes)
    monkeypatch.setattr(atualizar, "tamanhos", lambda _m: tamanhos)


def test_nada_a_fazer_quando_ja_e_o_mes_mais_recente(monkeypatch, capsys, tmp_path):
    _sem_rede(monkeypatch, mes=atualizar.referencia_atual())
    assert atualizar.main(["--base", str(tmp_path)]) == 0
    assert "Nada a fazer" in capsys.readouterr().out


def test_avisa_e_nao_faz_nada_sem_confirmacao(monkeypatch, capsys, tmp_path):
    _sem_rede(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _p: "não")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    chamou = []
    monkeypatch.setattr(atualizar.subprocess, "run", lambda *a, **k: chamou.append(a))
    assert atualizar.main(["--base", str(tmp_path)]) == 1
    saida = capsys.readouterr().out
    assert "Vai BAIXAR" in saida and "vai APAGAR" in saida and "Memória" in saida
    assert "Cancelado" in saida
    assert chamou == []  # nada baixado


def test_sem_terminal_exige_confirmar_sim(monkeypatch, capsys, tmp_path):
    _sem_rede(monkeypatch)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert atualizar.main(["--base", str(tmp_path)]) == 1
    assert "CONFIRMAR=sim" in capsys.readouterr().out


def test_apaga_so_os_arquivos_baixados(tmp_path):
    for nome in atualizar.ARQUIVOS:
        (tmp_path / nome).write_bytes(b"x")
    (tmp_path / "meu-arquivo.txt").write_text("fica")
    atualizar.apagar_download(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["meu-arquivo.txt"]
