from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import redis

from app.services import cache_diario, feriados

AGORA = datetime(2026, 10, 27, 22, 0, tzinfo=cache_diario.FUSO_HORARIO)


class RedisFalso:
    """Simula o subconjunto do cliente Redis usado pelo cache."""

    def __init__(self):
        self.dados = {}
        self.expiracoes = {}

    def get(self, chave):
        return self.dados.get(chave)

    def set(self, chave, valor, ex=None):
        self.dados[chave] = valor
        self.expiracoes[chave] = ex


def test_memoria_expira_a_meia_noite():
    with patch.object(cache_diario, "_agora", return_value=AGORA):
        cache_diario.salvar("x", {"a": 1})
        assert cache_diario.obter("x") == {"a": 1}

    with patch.object(cache_diario, "_agora", return_value=AGORA + timedelta(hours=2)):
        assert cache_diario.obter("x") is None


def test_memoria_respeita_ttl():
    with patch.object(cache_diario, "_agora", return_value=AGORA):
        cache_diario.salvar("x", [1], ttl_segundos=60)
    with patch.object(cache_diario, "_agora", return_value=AGORA + timedelta(seconds=61)):
        assert cache_diario.obter("x") is None


def test_redis_grava_json_com_expiracao_ate_meia_noite():
    falso = RedisFalso()
    with patch.object(cache_diario, "_obter_cliente", return_value=falso), \
            patch.object(cache_diario, "_agora", return_value=AGORA):
        cache_diario.salvar("feriados:nacionais:2026", {"25/12/2026": "Natal"})
        valor = cache_diario.obter("feriados:nacionais:2026")

    chave = cache_diario.PREFIXO_CHAVE + "feriados:nacionais:2026"
    assert valor == {"25/12/2026": "Natal"}
    assert falso.expiracoes[chave] == 2 * 3600
    assert cache_diario._cache_memoria == {}


def test_redis_indisponivel_usa_memoria():
    cliente = MagicMock()
    cliente.get.side_effect = redis.ConnectionError("offline")
    cliente.set.side_effect = redis.ConnectionError("offline")
    with patch.object(cache_diario, "_obter_cliente", return_value=cliente):
        cache_diario.salvar("x", "valor")
        assert cache_diario.obter("x") == "valor"


def test_feriados_consulta_api_uma_vez_por_dia():
    falso = RedisFalso()
    resposta = MagicMock()
    resposta.json.return_value = {
        "feriados": [{"data": "25/12/2026", "nome": "Natal", "tipo": "NACIONAL"}],
        "meta": {"total_pages": 1},
    }
    with patch.object(cache_diario, "_obter_cliente", return_value=falso), \
            patch.object(feriados.settings, "FERIADOS_API_KEY", "chave"), \
            patch("app.services.feriados.requests.get", return_value=resposta) as mock_get:
        feriados.buscar_feriados_ano(2026)
        feriados.buscar_feriados_ano(2026)
        feriados.buscar_feriados_estaduais("TO", 2026)
        feriados.buscar_feriados_estaduais("TO", 2026)

    assert mock_get.call_count == 2


def test_feriados_de_fallback_expiram_antes():
    falso = RedisFalso()
    resposta = MagicMock()
    resposta.json.return_value = [{"date": "2026-12-25", "name": "Natal"}]

    def fake_get(url, **kwargs):
        if "feriadosapi" in url:
            raise feriados.requests.ConnectionError("offline")
        return resposta

    with patch.object(cache_diario, "_obter_cliente", return_value=falso), \
            patch.object(feriados.settings, "FERIADOS_API_KEY", "chave"), \
            patch("app.services.feriados.requests.get", side_effect=fake_get):
        feriados.buscar_feriados_ano(2026)

    chave = cache_diario.PREFIXO_CHAVE + "feriados:nacionais:2026"
    assert falso.expiracoes[chave] == feriados.TTL_FALLBACK_SEGUNDOS
