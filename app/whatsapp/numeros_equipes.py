import logging
import os
import re
from typing import Optional, Tuple

from dotenv import load_dotenv

import pandas as pd

load_dotenv()

def limpar_numero_br(numero):
    # Remove tudo que não for dígito
    numero = re.sub(r'\D', '', str(numero))

    # Remove prefixo +55, 0055 ou apenas 55
    if numero.startswith('0055'):
        numero = numero[4:]
    elif numero.startswith('55'):
        numero = numero[2:]

    # Se sobrou exatamente 11 dígitos (com 9 depois do DDD), remove o 9
    if len(numero) == 11 and numero[2] == '9':
        numero = numero[:2] + numero[3:]

    # Se agora temos 10 dígitos (DDXXXXXXXX), adiciona prefixo 55
    if len(numero) == 10:
        numero = '55' + numero

    # Valida se está no formato correto final
    if numero.startswith('55') and len(numero) == 12:
        return numero

    # Se não for válido, retorna vazio
    return ''

def _extrair_sheet_id(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrai o sheet_id e o gid (opcional) de uma URL de Google Sheets."""
    if not url:
        return None, None
    match = re.search(r"/d/([^/]+)/", url)
    sheet_id = match.group(1) if match else None
    gid_match = re.search(r"[?&]gid=(\\d+)", url)
    gid = gid_match.group(1) if gid_match else None
    return sheet_id, gid


def _carregar_via_gspread(sheet_id: str, worksheet_title: Optional[str], gid: Optional[str]) -> pd.DataFrame:
    from app.services.google_sheets import _carregar_credenciais
    import gspread

    client = gspread.authorize(_carregar_credenciais())
    spreadsheet = client.open_by_key(sheet_id)

    worksheet = None
    if worksheet_title:
        worksheet = spreadsheet.worksheet(worksheet_title)
    elif gid:
        try:
            worksheet = spreadsheet.get_worksheet(int(gid))
        except Exception:
            # fallback para procurar pelo gid na lista
            for ws in spreadsheet.worksheets():
                if str(ws.id) == str(gid):
                    worksheet = ws
                    break
    if worksheet is None:
        worksheet = spreadsheet.sheet1

    linhas = worksheet.get_all_values()
    if not linhas:
        raise ValueError("Planilha de equipes vazia.")
    cabecalho = linhas[0]
    dados = linhas[1:] if len(linhas) > 1 else []
    if len(cabecalho) < 2:
        raise ValueError("Planilha de equipes precisa de ao menos duas colunas.")

    df = pd.DataFrame(dados, columns=[str(c) for c in cabecalho])
    # Mantém apenas as duas primeiras colunas
    df = df.iloc[:, :2]
    df.columns = ["Equipe", "Numero"]
    return df


def _carregar_dataframe_equipes() -> pd.DataFrame:
    url = (os.getenv("PLANILHA_EQUIPES_URL") or "").strip()
    sheet_id_env = (os.getenv("PLANILHA_EQUIPES_SHEET_ID") or "").strip()
    worksheet_env = (os.getenv("PLANILHA_EQUIPES_WORKSHEET") or "").strip() or None

    sheet_id_url, gid_url = _extrair_sheet_id(url)
    sheet_id = sheet_id_env or sheet_id_url
    gid = (os.getenv("PLANILHA_EQUIPES_GID") or "").strip() or gid_url

    # 1) Tenta CSV público (mais rápido)
    if url:
        try:
            return pd.read_csv(url, usecols=[0, 1], skiprows=1)
        except Exception as exc:
            logging.warning("Falha ao ler planilha de equipes via CSV (%s): %s", url, exc)

    # 2) Fallback para Google Sheets API (service account)
    if not sheet_id:
        raise ValueError(
            "PLANILHA_EQUIPES_URL inválida e PLANILHA_EQUIPES_SHEET_ID não definido. "
            "Defina ao menos o sheet_id para usar o fallback via Google Sheets."
        )

    try:
        return _carregar_via_gspread(sheet_id, worksheet_env, gid)
    except Exception as exc:
        logging.exception("Falha ao ler planilha de equipes via Google Sheets API: %s", exc)
        raise


def carregar_numeros_equipes():
    df = _carregar_dataframe_equipes()

    # Renomear colunas
    df.columns = ['Equipe', 'Numero']

    # Remover linhas com célula vazia em Equipe ou Numero
    df.dropna(subset=['Equipe', 'Numero'], inplace=True)

    # Padronizar nomes das equipes
    df['Equipe'] = df['Equipe'].astype(str).str.strip().str.upper()

    # Aplicar limpeza aos números
    df['Numero'] = df['Numero'].apply(limpar_numero_br)

    # Remover linhas com números vazios ou inválidos
    df = df[df['Numero'] != '']

    # Retorna um dicionário: {'OPS': '556399999999', 'LOJA 75': '556398887777'}
    return dict(zip(df['Equipe'], df['Numero']))
