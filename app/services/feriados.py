"""Integração com a BrasilAPI para consulta de feriados nacionais.

Documentação: https://brasilapi.com.br/docs#tag/Feriados-Nacionais
"""

import logging
import threading
from datetime import datetime
from typing import Dict, Iterable, List

import pandas as pd
import requests

BRASILAPI_FERIADOS_URL = "https://brasilapi.com.br/api/feriados/v1/{ano}"
TIPOS_RELATORIO_COM_FERIADO = {"Auditoria", "Ocorrências"}
FORMATO_DATA = "%d/%m/%Y"

_cache_feriados: Dict[int, Dict[str, str]] = {}
_cache_lock = threading.Lock()


def buscar_feriados_ano(ano: int) -> Dict[str, str]:
    """Retorna os feriados nacionais do ano no formato {"dd/mm/aaaa": nome}.

    O resultado é mantido em cache por processo. Em caso de falha na API,
    retorna um dicionário vazio (sem cachear) para não bloquear o envio.
    """
    with _cache_lock:
        if ano in _cache_feriados:
            return _cache_feriados[ano]

    try:
        resp = requests.get(BRASILAPI_FERIADOS_URL.format(ano=ano), timeout=10)
        resp.raise_for_status()
        dados = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logging.warning("Não foi possível consultar feriados de %s na BrasilAPI: %s", ano, exc)
        return {}

    feriados: Dict[str, str] = {}
    for item in dados if isinstance(dados, list) else []:
        try:
            data = datetime.strptime(str(item.get("date", "")), "%Y-%m-%d")
        except ValueError:
            continue
        feriados[data.strftime(FORMATO_DATA)] = str(item.get("name", "")).strip() or "Feriado"

    with _cache_lock:
        _cache_feriados[ano] = feriados
    return feriados


def identificar_feriados(datas: Iterable[object]) -> Dict[str, str]:
    """Retorna os feriados presentes em uma lista de datas "dd/mm/aaaa"."""
    datas_validas = set()
    for valor in datas:
        texto = str(valor).strip()
        try:
            datas_validas.add(datetime.strptime(texto, FORMATO_DATA))
        except ValueError:
            continue

    encontrados: Dict[str, str] = {}
    for ano in sorted({data.year for data in datas_validas}):
        feriados_ano = buscar_feriados_ano(ano)
        for data in datas_validas:
            chave = data.strftime(FORMATO_DATA)
            if data.year == ano and chave in feriados_ano:
                encontrados[chave] = feriados_ano[chave]
    return dict(sorted(encontrados.items(), key=lambda item: datetime.strptime(item[0], FORMATO_DATA)))


def listar_feriados_df(df: pd.DataFrame) -> List[Dict[str, str]]:
    """Lista os feriados encontrados na coluna "Data" do DataFrame."""
    if df.empty or "Data" not in df.columns:
        return []
    feriados = identificar_feriados(df["Data"].dropna().unique())
    return [{"data": data, "nome": nome} for data, nome in feriados.items()]


def remover_datas_feriado(df: pd.DataFrame, feriados: Dict[str, str]) -> pd.DataFrame:
    """Remove do DataFrame as linhas cuja coluna "Data" é feriado."""
    if df.empty or not feriados or "Data" not in df.columns:
        return df
    mascara = df["Data"].astype(str).str.strip().isin(feriados.keys())
    return df[~mascara].copy()


def gerar_rodape_feriados() -> str:
    """Gera o rodapé em itálico (WhatsApp) pedindo para ignorar datas de feriado local.

    Usado quando os feriados nacionais são excluídos do envio, já que feriados
    estaduais/municipais não são mapeados pela BrasilAPI.
    """
    return (
        "_Obs.: Caso alguma das datas acima seja feriado estadual ou municipal "
        "na sua localidade, favor desconsiderá-la._"
    )
