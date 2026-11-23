import pytest

from app.services.library_service import LIBRARY


@pytest.fixture(autouse=True)
def biblioteca_limpa():
    """Cada teste começa sem lançamentos, arquivos, contas nem decisões na memória da API."""
    LIBRARY.reset()
    yield
    LIBRARY.reset()


@pytest.fixture(autouse=True)
def sem_persistencia(monkeypatch):
    """Os testes não gravam a biblioteca no ``trokim.db`` real; os de persistência passam
    o próprio repositório."""
    from app.services import library_store

    library_store.configure(None)
    monkeypatch.setattr(library_store.settings, "LIBRARY_PERSISTENCE", False)
    yield
    library_store.configure(None)


@pytest.fixture(autouse=True)
def sem_indice_cnpj(request, monkeypatch):
    """Por padrão, os testes não consultam o índice CNPJ real (versionado no repositório).

    Um CNPJ inventado numa fixture pode coincidir com o de uma empresa real e mudar a
    categoria. Os testes que querem o índice real usam ``@pytest.mark.indice_cnpj_real``.
    """
    if request.node.get_closest_marker("indice_cnpj_real"):
        yield
        return
    from app.services import cnpj_index

    monkeypatch.setattr(cnpj_index, "get_index", lambda: None)
    yield
