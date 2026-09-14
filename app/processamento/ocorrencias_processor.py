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


def processar_ocorrencias(df: pd.DataFrame) -> pd.Series:
    # Lógica para processar as colunas 'Motivo' e 'Ação pendente'
    # e gerar as mensagens específicas para o relatório de ocorrências.
    # Esta função será chamada pelo controller.
    
    def gerar_linha_ocorrencia(row) -> Optional[str]:
        nome = row["Nome"]
        motivo = row["Motivo"]
        acao_pendente = row["Ação pendente"]

        if not validar_motivo(motivo):
            return None
        
        if motivo == "Número de pontos menor que o previsto" and acao_pendente == "Gestor aprovar solicitação de ajuste":
            return (
                f"*{nome}* solicitou ajuste.\n"
                f"Ação pendente: *{acao_pendente}*."
            )
        elif motivo == "Número de pontos menor que o previsto" and acao_pendente == "Gestor corrigir lançamento de exceção":
            return (
                f"*{nome}* apresentou _{motivo.lower()}_.\n"
                f"Ação pendente: *{acao_pendente}*."
            )
        elif motivo == "Número de pontos menor que o previsto":
            return (
                f"*{nome}* está com o _{motivo.lower()}_.\n"
                f"Ação pendente: *{acao_pendente}*."
            )
        elif motivo == "Número errado de pontos":
            return (
                f"*{nome}* apresentou _{motivo.lower()}_.\n"
                f"Ação pendente: *{acao_pendente}*."
            )
        else:
            return (
                f"*{nome}* _{motivo.lower()}_.\n"
                f"Ação pendente: *{acao_pendente}*."
            )

    # Agrupar por Nome e Data para consolidar as mensagens por ocorrência
    def compilar_mensagens(grupo: pd.DataFrame) -> Optional[MensagemDetalhada]:
        textos: List[str] = []
        motivos: List[str] = []
        for _, row in grupo.iterrows():
            mensagem = gerar_linha_ocorrencia(row)
            if not mensagem:
                continue
            textos.append(mensagem)
            motivo = row.get("Motivo")
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
