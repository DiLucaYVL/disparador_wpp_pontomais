"""Cache diário (Redis) para respostas de APIs externas e planilhas.

Os valores são gravados como JSON e expiram à meia-noite (horário de
Brasília), de modo que cada consulta externa é feita no máximo uma vez por
dia, compartilhada entre todos os workers do Gunicorn. Se o Redis estiver
indisponível, usa um cache em memória do processo com a mesma validade.
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import redis

from app.config import settings

PREFIXO_CHAVE = "disparador:cache:"
FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")

_cliente: Optional[redis.Redis] = None
_cache_memoria: Dict[str, Tuple[datetime, Any]] = {}
_lock = threading.Lock()


def _agora() -> datetime:
    return datetime.now(FUSO_HORARIO)


def _proxima_meia_noite(agora: datetime) -> datetime:
    amanha = (agora + timedelta(days=1)).date()
    return datetime(amanha.year, amanha.month, amanha.day, tzinfo=FUSO_HORARIO)


def _obter_cliente() -> Optional[redis.Redis]:
    """Retorna o cliente Redis (criado sob demanda) ou ``None`` se não configurado."""
    global _cliente
    if not settings.REDIS_URL:
        return None
    with _lock:
        if _cliente is None:
            _cliente = redis.Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
        return _cliente


def obter(chave: str) -> Optional[Any]:
    """Retorna o valor em cache para ``chave`` ou ``None`` se ausente/expirado."""
    cliente = _obter_cliente()
    if cliente is not None:
        try:
            bruto = cliente.get(PREFIXO_CHAVE + chave)
            return json.loads(bruto) if bruto is not None else None
        except (redis.RedisError, ValueError) as exc:
            logging.warning("Redis indisponível ao ler cache %s; usando memória: %s", chave, exc)

    with _lock:
        item = _cache_memoria.get(chave)
        if item is None:
            return None
        expira_em, valor = item
        if _agora() >= expira_em:
            del _cache_memoria[chave]
            return None
        return valor


def salvar(chave: str, valor: Any, ttl_segundos: Optional[int] = None) -> None:
    """Grava ``valor`` (serializável em JSON) até a meia-noite ou por ``ttl_segundos``."""
    agora = _agora()
    if ttl_segundos is None:
        expira_em = _proxima_meia_noite(agora)
    else:
        expira_em = agora + timedelta(seconds=ttl_segundos)
    segundos = max(1, int((expira_em - agora).total_seconds()))

    cliente = _obter_cliente()
    if cliente is not None:
        try:
            cliente.set(PREFIXO_CHAVE + chave, json.dumps(valor, ensure_ascii=False), ex=segundos)
            return
        except redis.RedisError as exc:
            logging.warning("Redis indisponível ao gravar cache %s; usando memória: %s", chave, exc)

    with _lock:
        _cache_memoria[chave] = (expira_em, valor)


def limpar_memoria() -> None:
    """Esvazia o cache em memória (usado nos testes)."""
    with _lock:
        _cache_memoria.clear()
