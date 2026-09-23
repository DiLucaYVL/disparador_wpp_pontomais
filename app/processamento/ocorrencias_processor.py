from typing import List, Optional

import pandas as pd
from app.types import MensagemDetalhada

from .motivos_ocorrencias import validar_motivo, eh_pendencia_gestor


def filtrar_pendencia_gestor(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna apenas as linhas cuja 'Ação pendente' depende do gestor.

    Usado pelo checkbox "Enviar apenas pendências do gestor" (relatório de
    Ocorrências): ocorrências que dependem do colaborador (ex.: "Colaborador
    solicitar ajuste") não devem gerar mensagem nem ser registradas.
    """
    if df.empty or "Ação pendente" not in df.columns:
        return df
    return df[df["Ação pendente"].apply(eh_pendencia_gestor)]


def gerar_linha_ocorrencia(row) -> Optional[str]:
    """Gera o texto da mensagem para uma ocorrência específica."""
    nome = row.get("Nome", "")
    motivo = row.get("Motivo")
    if not motivo and "Ocorrência" in row:
        motivo = row.get("Ocorrência")
    acao_pendente = row.get("Ação pendente")
    if not acao_pendente and "Valor" in row:
        acao_pendente = row.get("Valor")

    if not isinstance(motivo, str) or not validar_motivo(motivo.strip()):
        return None

    motivo = motivo.strip()
    acao_pendente = (
        str(acao_pendente).strip()
        if acao_pendente is not None and str(acao_pendente).strip() not in {"nan", "None"}
        else ""
    )

    acao_texto = f"\nAção pendente: *{acao_pendente}*." if acao_pendente else ""
    if motivo == "Número de pontos menor que o previsto" and acao_pendente == "Gestor aprovar solicitação de ajuste":
        return f"*{nome}* solicitou ajuste.{acao_texto}"
    elif motivo == "Número de pontos menor que o previsto" and acao_pendente == "Gestor corrigir lançamento de exceção":
        return f"*{nome}* apresentou _{motivo.lower()}_.{acao_texto}"
    elif motivo == "Número de pontos menor que o previsto":
        return f"*{nome}* está com o _{motivo.lower()}_.{acao_texto}"
    elif motivo == "Número errado de pontos":
        return f"*{nome}* apresentou _{motivo.lower()}_.{acao_texto}"
    else:
        return f"*{nome}* _{motivo.lower()}_.{acao_texto}"


def processar_ocorrencias(df: pd.DataFrame) -> pd.Series:
    """Processa DataFrame de ocorrências e gera mensagens agrupadas por Nome e Data."""
    def compilar_mensagens(grupo: pd.DataFrame) -> Optional[MensagemDetalhada]:
        textos: List[str] = []
        motivos: List[str] = []
        for _, row in grupo.iterrows():
            mensagem = gerar_linha_ocorrencia(row)
            if not mensagem:
                continue
            textos.append(mensagem)
            motivo = row.get("Motivo") or row.get("Ocorrência")
            if isinstance(motivo, str):
                motivo_limpo = motivo.strip()
                if motivo_limpo and motivo_limpo not in motivos:
                    motivos.append(motivo_limpo)

        if not textos:
            return None

        return MensagemDetalhada(
            texto="\n".join(textos),
            motivos=motivos,
        )

    indices = []
    valores = []
    for (nome_grupo, data_grupo), grupo in df.groupby(["Nome", "Data"], sort=False):
        checado = compilar_mensagens(grupo)
        if checado is not None:
            indices.append((nome_grupo, data_grupo))
            valores.append(checado)

    if not valores:
        return pd.Series(dtype=object)

    return pd.Series(
        valores,
        index=pd.MultiIndex.from_tuples(indices, names=["Nome", "Data"]),
    )
