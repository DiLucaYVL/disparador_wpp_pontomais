"""Consulta de feriados nacionais com fallback entre fontes.

Ordem de consulta:
1. BrasilAPI: https://brasilapi.com.br/docs#tag/Feriados-Nacionais
2. Nager.Date: https://date.nager.at (apenas feriados com ``global=True``)
3. Cálculo local (datas fixas + móveis derivadas da Páscoa), sem rede.
"""

import logging
import threading
from datetime import date, datetime, timedelta
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

BRASILAPI_FERIADOS_URL = "https://brasilapi.com.br/api/feriados/v1/{ano}"
NAGER_FERIADOS_URL = "https://date.nager.at/api/v3/PublicHolidays/{ano}/BR"
TIMEOUT_API_SEGUNDOS = 5
TIPOS_RELATORIO_COM_FERIADO = {"Auditoria", "Ocorrências"}
FORMATO_DATA = "%d/%m/%Y"

FERIADOS_FIXOS = [
    (1, 1, "Confraternização mundial"),
    (4, 21, "Tiradentes"),
    (5, 1, "Dia do trabalho"),
    (9, 7, "Independência do Brasil"),
    (10, 12, "Nossa Senhora Aparecida"),
    (11, 2, "Finados"),
    (11, 15, "Proclamação da República"),
    (12, 25, "Natal"),
]
# Deslocamento em dias a partir do domingo de Páscoa.
FERIADOS_MOVEIS = [
    (-48, "Carnaval"),
    (-47, "Carnaval"),
    (-2, "Sexta-feira Santa"),
    (0, "Páscoa"),
    (60, "Corpus Christi"),
]
ANO_INICIO_CONSCIENCIA_NEGRA = 2024  # Lei 14.759/2023

_cache_feriados: Dict[int, Dict[str, str]] = {}
_cache_lock = threading.Lock()


def _converter_lista_api(dados: object, campo_nome: str) -> Dict[str, str]:
    """Converte a lista [{"date": "aaaa-mm-dd", ...}] em {"dd/mm/aaaa": nome}."""
    feriados: Dict[str, str] = {}
    for item in dados if isinstance(dados, list) else []:
        try:
            data = datetime.strptime(str(item.get("date", "")), "%Y-%m-%d")
        except ValueError:
            continue
        feriados[data.strftime(FORMATO_DATA)] = str(item.get(campo_nome, "")).strip() or "Feriado"
    return feriados


def _buscar_brasilapi(ano: int) -> Dict[str, str]:
    resp = requests.get(BRASILAPI_FERIADOS_URL.format(ano=ano), timeout=TIMEOUT_API_SEGUNDOS)
    resp.raise_for_status()
    return _converter_lista_api(resp.json(), "name")


def _buscar_nager(ano: int) -> Dict[str, str]:
    resp = requests.get(NAGER_FERIADOS_URL.format(ano=ano), timeout=TIMEOUT_API_SEGUNDOS)
    resp.raise_for_status()
    dados = resp.json()
    nacionais = [item for item in dados if isinstance(item, dict) and item.get("global")]
    return _converter_lista_api(nacionais, "localName")


def calcular_pascoa(ano: int) -> date:
    """Calcula o domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes, dia = divmod(h + l_ - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def calcular_feriados_locais(ano: int) -> Dict[str, str]:
    """Calcula os feriados nacionais sem depender de rede."""
    feriados = {date(ano, mes, dia): nome for mes, dia, nome in FERIADOS_FIXOS}
    if ano >= ANO_INICIO_CONSCIENCIA_NEGRA:
        feriados[date(ano, 11, 20)] = "Dia da consciência negra"
    pascoa = calcular_pascoa(ano)
    for deslocamento, nome in FERIADOS_MOVEIS:
        feriados[pascoa + timedelta(days=deslocamento)] = nome
    return {data.strftime(FORMATO_DATA): nome for data, nome in sorted(feriados.items())}


FONTES_FERIADOS: List[Tuple[str, Callable[[int], Dict[str, str]]]] = [
    ("BrasilAPI", _buscar_brasilapi),
    ("Nager.Date", _buscar_nager),
]


def buscar_feriados_ano(ano: int) -> Dict[str, str]:
    """Retorna os feriados nacionais do ano no formato {"dd/mm/aaaa": nome}.

    Tenta cada API em ``FONTES_FERIADOS`` e, se todas falharem, usa o
    cálculo local. O resultado é mantido em cache por processo.
    """
    with _cache_lock:
        if ano in _cache_feriados:
            return _cache_feriados[ano]

    feriados: Optional[Dict[str, str]] = None
    for nome_fonte, fonte in FONTES_FERIADOS:
        try:
            feriados = fonte(ano) or None
        except (requests.RequestException, ValueError) as exc:
            logging.warning("Não foi possível consultar feriados de %s na %s: %s", ano, nome_fonte, exc)
            continue
        if feriados:
            break
        logging.warning("%s retornou lista vazia de feriados para %s.", nome_fonte, ano)

    if not feriados:
        logging.warning("APIs de feriados indisponíveis; usando cálculo local para %s.", ano)
        feriados = calcular_feriados_locais(ano)

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
