from unittest.mock import patch

import pytest

from app.services import cache_diario


@pytest.fixture(autouse=True)
def cache_em_memoria():
    """Isola os testes do Redis real: usa apenas o cache em memória, limpo a cada teste."""
    cache_diario.limpar_memoria()
    with patch.object(cache_diario.settings, "REDIS_URL", ""):
        yield
    cache_diario.limpar_memoria()
