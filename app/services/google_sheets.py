"""Integração com Google Sheets.

As funções abaixo permitem registrar o DataFrame processado na planilha
configurada por variáveis de ambiente.
"""

import json
import logging
import re
from typing import Optional

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from app.config.settings import (
    GOOGLE_SHEETS_CREDENTIALS_FILE,
    GOOGLE_SHEETS_CREDENTIALS_JSON,
    GOOGLE_SHEETS_ENABLED,
    GOOGLE_SHEETS_SPREADSHEET_ID,
    GOOGLE_SHEETS_WORKSHEET,
)
from app.processamento.ocorrencias_processor import processar_ocorrencias
from app.whatsapp.mensagem import gerar_mensagens
from app.types import MensagemDetalhada

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DATE_REGEX = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$")


def _carregar_credenciais() -> Credentials:
    """Monta as credenciais do serviço a partir do arquivo ou JSON."""
    if GOOGLE_SHEETS_CREDENTIALS_FILE:
        return Credentials.from_service_account_file(
            GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=SCOPES
        )

    if GOOGLE_SHEETS_CREDENTIALS_JSON:
        try:
            info = json.loads(GOOGLE_SHEETS_CREDENTIALS_JSON)
        except json.JSONDecodeError as exc:  # noqa: PERF203
            raise ValueError(
                "GOOGLE_SHEETS_CREDENTIALS_JSON inválido. Verifique o JSON fornecido."
            ) from exc

        return Credentials.from_service_account_info(info, scopes=SCOPES)

    raise ValueError(
        "Credenciais do Google Sheets não configuradas. "
        "Defina GOOGLE_SHEETS_CREDENTIALS_FILE ou GOOGLE_SHEETS_CREDENTIALS_JSON."
    )


def _normalizar_valor_chave(valor: object) -> str:
    texto = str(valor).strip()
    match = DATE_REGEX.match(texto)
    if match:
        dia, mes, ano = match.groups()
        ano_int = int(ano)
        if ano_int < 100:
            ano_int += 2000
        try:
            return f"{int(dia):02d}/{int(mes):02d}/{ano_int:04d}"
        except ValueError:
            pass
    if texto.isdigit():
        try:
            return str(int(texto))
        except ValueError:
            return texto.upper()
    return texto.upper()


def _linha_chave(cells: list, tamanho: int) -> tuple:
    """Normaliza uma linha para comparação (dedup em planilha)."""
    if len(cells) < tamanho:
        cells = list(cells) + [""] * (tamanho - len(cells))
    return tuple(_normalizar_valor_chave(valor) for valor in cells[:tamanho])


def registrar_dataframe_no_sheets(
    df: pd.DataFrame, *, tipo_relatorio: str, nome_relatorio: Optional[str] = None
) -> None:
    """Envia o DataFrame para o Google Sheets, adicionando linhas ao final.

    - Caso a aba esteja vazia, escreve o cabeçalho antes de inserir os dados.
    - Preenche automaticamente as colunas auxiliares TipoRelatorio e NomeRelatorio.
    - Evita duplicar linhas já existentes (usa todas as colunas como chave).
    """
    if not GOOGLE_SHEETS_ENABLED:
        logging.info("Google Sheets desabilitado. Nenhum dado será enviado.")
        return

    if not GOOGLE_SHEETS_SPREADSHEET_ID:
        logging.warning(
            "Google Sheets habilitado, mas GOOGLE_SHEETS_SPREADSHEET_ID não foi definido."
        )
        return

    df_normalizado = _normalizar_df_para_sheets(df, tipo_relatorio, nome_relatorio)
    if df_normalizado.empty:
        logging.info("DataFrame vazio após normalização; nada a registrar no Google Sheets.")
        return

    try:
        creds = _carregar_credenciais()
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)

        try:
            worksheet = spreadsheet.worksheet(GOOGLE_SHEETS_WORKSHEET)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=GOOGLE_SHEETS_WORKSHEET,
                rows=1000,
                cols=max(len(df.columns) + 2, 20),
            )

        dados = df_normalizado.fillna("")

        cabecalho = [str(col) for col in dados.columns.tolist()]
        primeira_linha = [celula.strip() for celula in worksheet.row_values(1)]
        if not any(primeira_linha):
            worksheet.update("A1", [cabecalho])
        elif primeira_linha != cabecalho:
            logging.warning(
                "Cabeçalho existente difere do DataFrame; mantendo cabeçalho atual."
            )

        valores = dados.astype(str).values.tolist()
        if valores:
            existentes = worksheet.get_all_values() or []
            logging.info(
                "Google Sheets: carregando existentes para dedupe - linhas=%s (cabecalho incluso)",
                len(existentes),
            )
            tamanho = len(cabecalho)
            # primeira linha é cabeçalho
            existentes_set = set()
            for linha in existentes[1:]:
                if not linha or not any(linha):
                    continue
                existentes_set.add(_linha_chave(linha, tamanho))

            novos_filtrados = []
            ignorados = 0
            for linha in valores:
                chave = _linha_chave(linha, tamanho)
                if chave in existentes_set:
                    ignorados += 1
                    continue
                existentes_set.add(chave)
                novos_filtrados.append(linha)

            if novos_filtrados:
                worksheet.append_rows(
                    novos_filtrados, value_input_option="USER_ENTERED"
                )
                logging.info(
                    "Registradas %s linhas (ignoradas %s duplicadas) no Google Sheets (%s / aba %s).",
                    len(novos_filtrados),
                    ignorados,
                    GOOGLE_SHEETS_SPREADSHEET_ID,
                    GOOGLE_SHEETS_WORKSHEET,
                )
            else:
                logging.info(
                    "Nenhuma nova linha para registrar (tudo já existente). Ignoradas %s duplicadas.",
                    ignorados,
                )
    except Exception as exc:  # noqa: BLE001
        logging.exception("Falha ao registrar dados no Google Sheets: %s", exc)
        raise
def _motivos_para_texto(motivos: Optional[list]) -> str:
    if not motivos:
        return ""
    # Remove duplicatas mantendo ordem
    vistos = []
    for item in motivos:
        if item not in vistos and item is not None:
            vistos.append(str(item).strip())
    return " | ".join([m for m in vistos if m])


def _extrair_registros_mensagem(
    df: pd.DataFrame,
    serie: pd.Series,
    tipo_relatorio: str,
    nome_relatorio: Optional[str],
) -> pd.DataFrame:
    def _padronizar_data(valor: object) -> str:
        texto = str(valor).strip()
        try:
            data = pd.to_datetime(texto, dayfirst=True, errors="raise")
            return data.strftime("%d/%m/%Y")
        except Exception:
            return texto

    registros = []
    for (nome, data), detalhe in serie.items():
        if not detalhe or not isinstance(detalhe, MensagemDetalhada):
            continue

        selecionado = df[(df["Nome"] == nome) & (df["Data"] == data)]
        equipe = ""
        equipe_tratada = ""
        if not selecionado.empty:
            equipe = str(selecionado["Equipe"].iloc[0]) if "Equipe" in selecionado else ""
            equipe_tratada = (
                str(selecionado["EquipeTratada"].iloc[0])
                if "EquipeTratada" in selecionado
                else ""
            )

        registros.append(
            {
                "TipoRelatorio": tipo_relatorio,
                "NomeRelatorio": nome_relatorio or "",
                "Nome": nome,
                "Equipe": equipe,
                "Data": _padronizar_data(data),
                "Motivo": _motivos_para_texto(detalhe.motivos),
                "EquipeTratada": equipe_tratada,
            }
        )

    colunas_final = [
        "TipoRelatorio",
        "NomeRelatorio",
        "Nome",
        "Equipe",
        "Data",
        "Motivo",
        "EquipeTratada",
    ]
    return pd.DataFrame(registros, columns=colunas_final)


def _normalizar_df_para_sheets(
    df: pd.DataFrame, tipo_relatorio: str, nome_relatorio: Optional[str]
) -> pd.DataFrame:
    """Normaliza qualquer relatório para o formato de exportação ao Sheets."""
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "TipoRelatorio",
                "NomeRelatorio",
                "Nome",
                "Equipe",
                "Data",
                "Motivo",
                "EquipeTratada",
            ]
        )

    tipo_norm = (tipo_relatorio or "").strip().lower()

    if tipo_norm == "auditoria":
        if "FaltaAbonadaJustificada" not in df.columns:
            df = df.copy()
            df["FaltaAbonadaJustificada"] = False
        serie = gerar_mensagens(df, "Auditoria")
        return _extrair_registros_mensagem(df, serie, "Auditoria", nome_relatorio)

    if tipo_norm in {"ocorrencias", "ocorrências"}:
        serie = processar_ocorrencias(df)
        return _extrair_registros_mensagem(df, serie, "Ocorrências", nome_relatorio)

    if tipo_norm == "assinaturas":
        registros = []
        def _padronizar_data_assinatura(valor: object) -> str:
            texto = str(valor).strip()
            try:
                data = pd.to_datetime(texto, dayfirst=True, errors="raise")
                return data.strftime("%d/%m/%Y")
            except Exception:
                return texto

        for _, row in df.iterrows():
            registros.append(
                {
                    "TipoRelatorio": "Assinaturas",
                    "NomeRelatorio": nome_relatorio or "",
                    "Nome": str(row.get("Nome", "")).strip(),
                    "Equipe": str(row.get("Equipe", "")).strip(),
                    "Data": _padronizar_data_assinatura(row.get("Período (Fechamento)", "")),
                    "Motivo": "Assinatura pendente",
                    "EquipeTratada": str(row.get("EquipeTratada", "")).strip(),
                }
            )
        return pd.DataFrame(
            registros,
            columns=[
                "TipoRelatorio",
                "NomeRelatorio",
                "Nome",
                "Equipe",
                "Data",
                "Motivo",
                "EquipeTratada",
            ],
        )

    raise ValueError(
        f"Tipo de relatório inválido para normalização no Sheets: {tipo_relatorio!r}"
    )
import re
