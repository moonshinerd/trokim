import pytest

from app.services.library_service import LIBRARY


@pytest.fixture(autouse=True)
def biblioteca_limpa():
    """Cada teste começa sem lançamentos, arquivos, contas nem decisões na memória da API."""
    LIBRARY.reset()
    yield
    LIBRARY.reset()
