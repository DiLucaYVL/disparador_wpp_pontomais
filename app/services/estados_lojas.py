"""Mapeamento do estado (UF) de cada equipe a partir da planilha de lojas.

A planilha é configurada pelas variáveis ``GOOGLE_SHEETS_LOJA_*``. A coluna B
contém a identificação da loja, normalizada com ``mapear_equipe`` (a mesma
normalização usada em ``EquipeTratada``). O estado é lido da coluna cujo
cabeçalho é "UF" ou "Estado". Setores (equipes que não são lojas) são
considerados de Tocantins (``TO``).
"""

import logging
import re
from typing import Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials

from app.config.settings import (
    GOOGLE_SHEETS_LOJA_ID,
    GOOGLE_SHEETS_LOJA_PRIVATE_KEY,
    GOOGLE_SHEETS_LOJA_SERVICE_ACCOUNT,
    GOOGLE_SHEETS_LOJA_WORKSHEET,
)
from app.processamento.mapear_gerencia import eh_loja, mapear_equipe
from app.services import cache_diario

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
ESTADO_SETORES = "TO"
INDICE_COLUNA_LOJA = 1  # Coluna B
CABECALHOS_ESTADO = {"UF", "ESTADO"}
CODIGO_LOJA_REGEX = re.compile(r"^[A-Z]?\d{1,3}[A-Z]?$")
PEM_REGEX = re.compile(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----", re.S)
CHAVE_CACHE = "planilha_lojas:estados"


def normalizar_chave_privada(chave: str) -> str:
    """Reconstrói a chave PEM vinda do ``.env`` (aspas, ``\\n`` escapados, linha única)."""
    chave = chave.strip().strip('"').strip("'").replace("\r", "")
    chave = re.sub(r"\\+n", "\n", chave)
    match = PEM_REGEX.search(chave)
    if not match:
        return chave
    tipo = match.group(1)
    corpo = re.sub(r"[^A-Za-z0-9+/=]", "", match.group(2))
    linhas = [corpo[i:i + 64] for i in range(0, len(corpo), 64)]
    return f"-----BEGIN {tipo}-----\n" + "\n".join(linhas) + f"\n-----END {tipo}-----\n"


def _carregar_credenciais() -> Credentials:
    if not (GOOGLE_SHEETS_LOJA_SERVICE_ACCOUNT and GOOGLE_SHEETS_LOJA_PRIVATE_KEY):
        raise ValueError(
            "Credenciais da planilha de lojas não configuradas. Defina "
            "GOOGLE_SHEETS_LOJA_SERVICE_ACCOUNT e GOOGLE_SHEETS_LOJA_PRIVATE_KEY."
        )
    info = {
        "type": "service_account",
        "client_email": GOOGLE_SHEETS_LOJA_SERVICE_ACCOUNT,
        "private_key": normalizar_chave_privada(GOOGLE_SHEETS_LOJA_PRIVATE_KEY),
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def _ler_linhas_planilha() -> List[List[str]]:
    if not GOOGLE_SHEETS_LOJA_ID:
        raise ValueError("GOOGLE_SHEETS_LOJA_ID não definido.")
    spreadsheet = gspread.authorize(_carregar_credenciais()).open_by_key(GOOGLE_SHEETS_LOJA_ID)
    if GOOGLE_SHEETS_LOJA_WORKSHEET:
        worksheet = spreadsheet.worksheet(GOOGLE_SHEETS_LOJA_WORKSHEET)
    else:
        worksheet = spreadsheet.sheet1
    return worksheet.get_all_values()


def normalizar_loja(valor: object) -> str:
    """Normaliza a identificação da loja com ``mapear_equipe``.

    Valores que trazem apenas o código (ex.: "75", "A1") recebem o prefixo
    "Loja" para que a normalização os reconheça.
    """
    texto = str(valor).strip()
    if not texto:
        return ""
    if not eh_loja(texto):
        texto = f"Loja {texto}"
    return mapear_equipe(texto)


def montar_mapa_estados(linhas: List[List[str]]) -> Dict[str, str]:
    """Monta {codigo_loja: UF} a partir das linhas da planilha (com cabeçalho)."""
    if not linhas:
        raise ValueError("Planilha de lojas vazia.")
    cabecalho = [str(celula).strip().upper() for celula in linhas[0]]
    indice_estado = next(
        (i for i, nome in enumerate(cabecalho) if nome in CABECALHOS_ESTADO), None
    )
    if indice_estado is None:
        raise ValueError("Planilha de lojas sem coluna de estado (cabeçalho 'UF' ou 'Estado').")

    mapa: Dict[str, str] = {}
    for linha in linhas[1:]:
        if len(linha) <= max(INDICE_COLUNA_LOJA, indice_estado):
            continue
        codigo = normalizar_loja(linha[INDICE_COLUNA_LOJA])
        estado = str(linha[indice_estado]).strip().upper()
        if not estado or not CODIGO_LOJA_REGEX.match(codigo):
            continue
        if codigo in mapa and mapa[codigo] != estado:
            logging.warning(
                "Loja %s aparece com estados diferentes (%s, %s); mantendo o primeiro.",
                codigo, mapa[codigo], estado,
            )
            continue
        mapa[codigo] = estado
    return mapa


def carregar_estados_lojas(forcar_atualizacao: bool = False) -> Dict[str, str]:
    """Retorna {codigo_loja: UF} lido da planilha de lojas (com cache diário)."""
    if not forcar_atualizacao:
        em_cache = cache_diario.obter(CHAVE_CACHE)
        if em_cache is not None:
            return em_cache

    mapa = montar_mapa_estados(_ler_linhas_planilha())
    cache_diario.salvar(CHAVE_CACHE, mapa)
    return mapa


def eh_codigo_loja(equipe_tratada: object) -> bool:
    """Indica se o valor de ``EquipeTratada`` é um código de loja (ex.: "75", "A1")."""
    return bool(CODIGO_LOJA_REGEX.match(str(equipe_tratada).strip().upper()))


def obter_estado_equipe(
    equipe_tratada: object, mapa_estados: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """Retorna a UF da equipe: setores são ``TO``; lojas vêm da planilha.

    Retorna ``None`` quando a loja não é encontrada na planilha.
    """
    codigo = str(equipe_tratada).strip().upper()
    if not eh_codigo_loja(codigo):
        return ESTADO_SETORES
    if mapa_estados is None:
        mapa_estados = carregar_estados_lojas()
    estado = mapa_estados.get(codigo)
    if estado is None:
        logging.warning("Loja %s não encontrada na planilha de lojas.", codigo)
    return estado
