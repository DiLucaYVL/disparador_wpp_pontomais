import pandas as pd
from .motivos_ocorrencias import validar_motivo

def processar_ocorrencias(df):
    # Lógica para processar as colunas 'Motivo' e 'Ação pendente'
    # e gerar as mensagens específicas para o relatório de ocorrências.
    # Esta função será chamada pelo controller.
    
    def gerar_linha_ocorrencia(row):
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
    mensagens_ocorrencias = (
        df.groupby(["Nome", "Data"], group_keys=False)
        .apply(
            lambda g: "\n".join(
                msg
                for _, row in g.iterrows()
                if (msg := gerar_linha_ocorrencia(row)) is not None
            )
        )
    )
    mensagens_ocorrencias = mensagens_ocorrencias.replace("", pd.NA).dropna()
    return mensagens_ocorrencias
