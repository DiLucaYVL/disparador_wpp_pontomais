import pandas as pd
from app.processamento.mapear_gerencia import mapear_equipe
from app.processamento.csv_reader_ocorrencias import carregar_dados_ocorrencias
from app.processamento.csv_reader_assinaturas import carregar_dados_assinaturas
from app.whatsapp.mensagem import validar_ocorrencia

def carregar_dados(caminho_csv, ignorar_sabados, tipo_relatorio):
    if tipo_relatorio == "Auditoria":
        df = pd.read_csv(caminho_csv, skiprows=3, skipfooter=12, engine="python")

        # === Ignorar determinados registros de sábado
        if ignorar_sabados:
            # Limpar e identificar sábados
            data_col = df["Data"].astype(str).str.replace("\"", "").str.strip().str.lower()
            df["DataLimpa"] = data_col
            df["DataFormatada"] = df["DataLimpa"].str[5:]

            # Filtro 1: Sábados com "Falta"
            is_sabado = data_col.str.startswith("sáb,")
            is_falta = df["Ocorrência"] == "Falta"
            is_sabado_falta = is_sabado & is_falta

            # Filtro 2: Sábados com "Horas Faltantes" == 04:00
            is_horas_faltantes = (df["Ocorrência"] == "Horas Faltantes") & (df["Valor"].astype(str).str.strip() == "04:00")
            is_sabado_horas_4 = is_sabado & is_horas_faltantes

            # Combinar datas e nomes para remoção
            remover_linhas = df[is_sabado_falta | is_sabado_horas_4][["Nome", "DataFormatada"]].drop_duplicates()
            df = df.merge(remover_linhas, on=["Nome", "DataFormatada"], how="left", indicator=True)
            df = df[df["_merge"] == "left_only"].drop(columns=["_merge"])

            # Atualizar a coluna final de Data
            df["Data"] = df["DataFormatada"]
        else:
            df["Data"] = df["Data"].astype(str).str.replace("\"", "").str[5:].str.strip()

        # === Marcar faltas abonadas/justificadas em vez de removê-las ===
        # Adiciona uma coluna temporária para indicar se a falta é abonada/justificada
        df["FaltaAbonadaJustificada"] = ((df["Ocorrência"] == "Falta") & 
        (df["Valor"].astype(str).str.lower().isin(["abonada", "justificada"])))

        df["EquipeTratada"] = df["Equipe"].apply(mapear_equipe)

        # Remover colunas temporárias se existirem
        df.drop(columns=["DataLimpa", "DataFormatada"], errors="ignore", inplace=True)

        df = df[df["Ocorrência"].apply(validar_ocorrencia)]

        equipes_validas = sorted(df["EquipeTratada"].dropna().unique().tolist())
        return df
    elif tipo_relatorio == "Ocorrências":
        return carregar_dados_ocorrencias(caminho_csv)
    elif tipo_relatorio == "Assinaturas":
        return carregar_dados_assinaturas(caminho_csv)
    else:
        raise ValueError("Tipo de relatório inválido. Escolha 'Auditoria', 'Ocorrências' ou 'Assinaturas'.")


