"""Consulta de feriados nacionais e estaduais com fallback entre fontes.

Ordem de consulta dos feriados nacionais:
1. FeriadosAPI: https://feriadosapi.com/docs (requer ``FERIADOS_API_KEY``)
2. BrasilAPI: https://brasilapi.com.br/docs#tag/Feriados-Nacionais
3. Nager.Date: https://date.nager.at (apenas feriados com ``global=True``)
4. Cálculo local (datas fixas + móveis derivadas da Páscoa), sem rede.

Feriados estaduais vêm apenas da FeriadosAPI, consultada pela UF de cada
equipe (``app/services/estados_lojas.py``). Se ela falhar, os estaduais são
ignorados.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

from app.config import settings
from app.services import cache_diario
from app.services.estados_lojas import (
    carregar_estados_lojas,
    eh_codigo_loja,
    obter_estado_equipe,
)

FERIADOSAPI_URL = "https://feriadosapi.com/api/v1/feriados/{caminho}"
FERIADOSAPI_LIMITE_POR_PAGINA = 100
TIPO_NACIONAL = "NACIONAL"
TIPO_ESTADUAL = "ESTADUAL"
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

# Resultados da fonte principal ficam em cache até a meia-noite; os de
# fallback expiram antes para que a FeriadosAPI seja consultada de novo.
TTL_FALLBACK_SEGUNDOS = 3600


def _requisitar_feriadosapi(caminho: str, ano: int) -> List[dict]:
    """Busca todas as páginas de um endpoint de feriados da FeriadosAPI."""
    chave = settings.FERIADOS_API_KEY
    if not chave:
        raise ValueError("FERIADOS_API_KEY não definida.")

    itens: List[dict] = []
    pagina = 1
    while True:
        resp = requests.get(
            FERIADOSAPI_URL.format(caminho=caminho),
            params={"ano": ano, "limit": FERIADOSAPI_LIMITE_POR_PAGINA, "page": pagina},
            headers={"Authorization": f"Bearer {chave}"},
            timeout=TIMEOUT_API_SEGUNDOS,
        )
        resp.raise_for_status()
        dados = resp.json()
        feriados = dados.get("feriados") if isinstance(dados, dict) else None
        if not isinstance(feriados, list):
            raise ValueError("Resposta inesperada da FeriadosAPI.")
        itens.extend(item for item in feriados if isinstance(item, dict))

        total_paginas = int((dados.get("meta") or {}).get("total_pages") or 1)
        if pagina >= total_paginas:
            return itens
        pagina += 1


def _converter_lista_feriadosapi(itens: List[dict], tipo: str) -> Dict[str, str]:
    """Filtra os feriados do ``tipo`` e converte para {"dd/mm/aaaa": nome}."""
    feriados: Dict[str, str] = {}
    for item in itens:
        if str(item.get("tipo", "")).strip().upper() != tipo:
            continue
        try:
            data = datetime.strptime(str(item.get("data", "")).strip(), FORMATO_DATA)
        except ValueError:
            continue
        feriados[data.strftime(FORMATO_DATA)] = str(item.get("nome", "")).strip() or "Feriado"
    return feriados


def _buscar_feriadosapi(ano: int) -> Dict[str, str]:
    return _converter_lista_feriadosapi(_requisitar_feriadosapi("nacionais", ano), TIPO_NACIONAL)


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
    ("FeriadosAPI", _buscar_feriadosapi),
    ("BrasilAPI", _buscar_brasilapi),
    ("Nager.Date", _buscar_nager),
]


def buscar_feriados_ano(ano: int) -> Dict[str, str]:
    """Retorna os feriados nacionais do ano no formato {"dd/mm/aaaa": nome}.

    Tenta cada API em ``FONTES_FERIADOS`` e, se todas falharem, usa o
    cálculo local. O resultado fica no cache diário (``cache_diario``).
    """
    chave_cache = f"feriados:nacionais:{ano}"
    em_cache = cache_diario.obter(chave_cache)
    if em_cache is not None:
        return em_cache

    feriados: Optional[Dict[str, str]] = None
    ttl: Optional[int] = TTL_FALLBACK_SEGUNDOS
    for posicao, (nome_fonte, fonte) in enumerate(FONTES_FERIADOS):
        try:
            feriados = fonte(ano) or None
        except (requests.RequestException, ValueError) as exc:
            logging.warning("Não foi possível consultar feriados de %s na %s: %s", ano, nome_fonte, exc)
            continue
        if feriados:
            if posicao == 0:
                ttl = None
            break
        logging.warning("%s retornou lista vazia de feriados para %s.", nome_fonte, ano)

    if not feriados:
        logging.warning("APIs de feriados indisponíveis; usando cálculo local para %s.", ano)
        feriados = calcular_feriados_locais(ano)

    cache_diario.salvar(chave_cache, feriados, ttl_segundos=ttl)
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


def buscar_feriados_estaduais(uf: str, ano: int) -> Dict[str, str]:
    """Retorna os feriados estaduais da UF no ano ({"dd/mm/aaaa": nome}).

    Usa a FeriadosAPI com cache diário; em caso de falha retorna vazio (sem
    cache, para que a próxima consulta tente de novo).
    """
    uf = uf.upper()
    chave_cache = f"feriados:estaduais:{uf}:{ano}"
    em_cache = cache_diario.obter(chave_cache)
    if em_cache is not None:
        return em_cache

    try:
        itens = _requisitar_feriadosapi(f"estado/{uf}", ano)
    except (requests.RequestException, ValueError) as exc:
        logging.warning("Não foi possível consultar feriados estaduais de %s/%s: %s", uf, ano, exc)
        return {}

    feriados = _converter_lista_feriadosapi(itens, TIPO_ESTADUAL)
    cache_diario.salvar(chave_cache, feriados)
    return feriados


def mapear_ufs_equipes(equipes: Iterable[object]) -> Dict[str, Optional[str]]:
    """Retorna {EquipeTratada: UF}; lojas sem estado conhecido ficam ``None``."""
    equipes_norm = {str(e).strip().upper() for e in equipes if str(e).strip()}
    mapa_lojas: Dict[str, str] = {}
    if any(eh_codigo_loja(equipe) for equipe in equipes_norm):
        try:
            mapa_lojas = carregar_estados_lojas()
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "Planilha de lojas indisponível; feriados estaduais das lojas serão ignorados: %s", exc
            )

    ufs: Dict[str, Optional[str]] = {}
    for equipe in equipes_norm:
        if eh_codigo_loja(equipe) and not mapa_lojas:
            ufs[equipe] = None
        else:
            ufs[equipe] = obter_estado_equipe(equipe, mapa_lojas)
    return ufs


def _ufs_por_linha(df: pd.DataFrame) -> pd.Series:
    """Série com a UF de cada linha, derivada de ``EquipeTratada``."""
    equipes = df["EquipeTratada"].astype(str).str.strip().str.upper()
    return equipes.map(mapear_ufs_equipes(equipes.unique()))


def identificar_feriados_estaduais(df: pd.DataFrame) -> Dict[Tuple[str, str], str]:
    """Retorna {(data, uf): nome} dos feriados estaduais presentes no relatório.

    Só considera a combinação de data e UF das equipes de cada linha.
    """
    if df.empty or not {"Data", "EquipeTratada"}.issubset(df.columns):
        return {}

    pares = set()
    for valor, uf in zip(df["Data"], _ufs_por_linha(df)):
        if not isinstance(uf, str) or not uf:
            continue
        try:
            data = datetime.strptime(str(valor).strip(), FORMATO_DATA)
        except ValueError:
            continue
        pares.add((data, uf))

    encontrados: Dict[Tuple[str, str], str] = {}
    for data, uf in sorted(pares):
        chave = data.strftime(FORMATO_DATA)
        nome = buscar_feriados_estaduais(uf, data.year).get(chave)
        if nome:
            encontrados[(chave, uf)] = nome
    return encontrados


def listar_feriados_df(df: pd.DataFrame) -> List[Dict[str, object]]:
    """Lista os feriados nacionais e estaduais encontrados no DataFrame.

    Feriados estaduais trazem também a UF e as equipes afetadas.
    """
    if df.empty or "Data" not in df.columns:
        return []
    lista: List[Dict[str, object]] = [
        {"data": data, "nome": nome, "tipo": "Nacional"}
        for data, nome in identificar_feriados(df["Data"].dropna().unique()).items()
    ]

    estaduais = identificar_feriados_estaduais(df)
    if estaduais:
        datas = df["Data"].astype(str).str.strip()
        ufs = _ufs_por_linha(df)
        equipes = df["EquipeTratada"].astype(str).str.strip().str.upper()
        for (data, uf), nome in estaduais.items():
            afetadas = sorted(equipes[(datas == data) & (ufs == uf)].unique().tolist())
            lista.append({"data": data, "nome": nome, "tipo": "Estadual", "uf": uf, "equipes": afetadas})

    lista.sort(key=lambda item: datetime.strptime(str(item["data"]), FORMATO_DATA))
    return lista


def remover_datas_feriado(
    df: pd.DataFrame,
    feriados: Dict[str, str],
    feriados_estaduais: Optional[Dict[Tuple[str, str], str]] = None,
) -> pd.DataFrame:
    """Remove as linhas em feriado nacional ou estadual (da UF da equipe)."""
    if df.empty or not (feriados or feriados_estaduais) or "Data" not in df.columns:
        return df
    datas = df["Data"].astype(str).str.strip()
    mascara = datas.isin(feriados.keys())
    if feriados_estaduais and "EquipeTratada" in df.columns:
        pares = pd.Series(list(zip(datas, _ufs_por_linha(df))), index=df.index)
        mascara |= pares.isin(set(feriados_estaduais))
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
