import pandas as pd
from app.processamento.mapear_gerencia import mapear_equipe


def carregar_dados_assinaturas(caminho_csv):
    """Carrega dados para o relatório de Assinaturas.

    - Ignora as 4 primeiras linhas e as 3 últimas.
    - Valida colunas necessárias.
    - Renomeia 'Colaborador' para 'Nome'.
    - Cria coluna 'EquipeTratada' usando ``mapear_equipe``.
    - Filtra apenas colaboradores com 'Assinado?' == 'Não'.
    - Mantém 'Período (Fechamento)' para composição das mensagens.
    """
    # Leitura do CSV considerando linhas a pular
    df = pd.read_csv(caminho_csv, skiprows=4, skipfooter=3, engine="python")

    # Validação de colunas obrigatórias
    colunas_necessarias = [
        "Colaborador",
        "Equipe",
        "Período (Fechamento)",
        "Assinado?",
    ]
    colunas_faltantes = [c for c in colunas_necessarias if c not in df.columns]
    if colunas_faltantes:
        raise ValueError(f"Colunas faltantes no arquivo CSV: {colunas_faltantes}")

    # Normalização e renomeação de colunas
    df.rename(columns={"Colaborador": "Nome"}, inplace=True)
    for coluna in ["Nome", "Equipe", "Período (Fechamento)", "Assinado?"]:
        df[coluna] = df[coluna].astype(str).str.strip()

    # Mapear equipes
    df["EquipeTratada"] = df["Equipe"].apply(mapear_equipe)

    # Filtrar apenas colaboradores não assinados
    df = df[df["Assinado?"].str.lower() == "não"]

    # Manter apenas colunas relevantes
    return df[["Nome", "Equipe", "EquipeTratada", "Período (Fechamento)"]]
