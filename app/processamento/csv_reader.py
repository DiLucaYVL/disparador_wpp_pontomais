import pandas as pd
from app.processamento.mapear_gerencia import mapear_equipe
from app.processamento.csv_reader_ocorrencias import carregar_dados_ocorrencias
from app.processamento.csv_reader_assinaturas import carregar_dados_assinaturas
from app.whatsapp.mensagem import validar_ocorrencia

def carregar_dados(caminho_csv, ignorar_sabados, tipo_relatorio):
    if tipo_relatorio == "Auditoria":
        with open(caminho_csv, encoding="utf-8", errors="replace") as _f:
            _linhas = _f.readlines()
        _total_linhas = len(_linhas)

        # Detecta dinamicamente a linha de cabeçalho das colunas (Nome, Equipe, Ocorrência, Motivo...)
        _linha_cabecalho = next(
            (
                i for i, l in enumerate(_linhas)
                if l.strip().startswith("Nome,")
                or ("Nome" in l and "Equipe" in l and ("Ocorrência" in l or "Ocorr" in l or "Motivo" in l))
            ),
            None,
        )
        _skiprows = _linha_cabecalho if _linha_cabecalho is not None else 3

        # Localiza a primeira linha que começa com "Resumo" ou "Total"
        _linha_resumo = next(
            (i for i, l in enumerate(_linhas) if i > _skiprows and (l.strip().startswith("Resumo") or l.strip().startswith("Total"))),
            None,
        )
        # Calcula quantas linhas cortar a partir do fim do arquivo.
        # Se "Resumo" não for encontrado, mantém 0 se o arquivo começar no cabeçalho ou fallback seguro (12).
        _skipfooter = (
            _total_linhas - _linha_resumo
            if _linha_resumo is not None
            else (0 if _linha_cabecalho == 0 else 12)
        )
        df = pd.read_csv(caminho_csv, skiprows=_skiprows, skipfooter=_skipfooter, engine="python")

        # === Ignorar determinados registros de sábado
        if ignorar_sabados:
            # Limpar e identificar sábados
            data_col = df["Data"].astype(str).str.replace("\"", "").str.strip().str.lower()
            df["DataLimpa"] = data_col
            df["DataFormatada"] = df["DataLimpa"].str.split(",").str[-1].str.strip()

            # Filtro 1: Sábados com "Falta"
            is_sabado = data_col.str.startswith("sáb,") | data_col.str.startswith("sab,")
            is_falta = (df["Ocorrência"] == "Falta") if "Ocorrência" in df.columns else False
            is_sabado_falta = is_sabado & is_falta

            # Filtro 2: Sábados com "Horas Faltantes" == 04:00
            is_horas_faltantes = (
                (df["Ocorrência"] == "Horas Faltantes") & (df["Valor"].astype(str).str.strip() == "04:00")
                if ("Ocorrência" in df.columns and "Valor" in df.columns)
                else False
            )
            is_sabado_horas_4 = is_sabado & is_horas_faltantes

            # Combinar datas e nomes para remoção
            remover_linhas = df[is_sabado_falta | is_sabado_horas_4][["Nome", "DataFormatada"]].drop_duplicates()
            df = df.merge(remover_linhas, on=["Nome", "DataFormatada"], how="left", indicator=True)
            df = df[df["_merge"] == "left_only"].drop(columns=["_merge"])

            # Atualizar a coluna final de Data
            df["Data"] = df["DataFormatada"]
        else:
            df["Data"] = df["Data"].astype(str).str.replace("\"", "").str.split(",").str[-1].str.strip()

        # === Marcar faltas abonadas/justificadas e normalizar interjornada ===
        if "Ocorrência" in df.columns and "Valor" in df.columns:
            df["FaltaAbonadaJustificada"] = (
                (df["Ocorrência"] == "Falta")
                & (df["Valor"].astype(str).str.lower().isin(["abonada", "justificada"]))
            )
            # Normalizar variações de interjornada exportadas pelo Pontomais
            mascara_inter = df["Ocorrência"].astype(str).str.contains("interjornada", case=False, na=False)
            df.loc[mascara_inter, "Ocorrência"] = "Interjornada insuficiente"
        else:
            df["FaltaAbonadaJustificada"] = False

        df["EquipeTratada"] = df["Equipe"].apply(mapear_equipe)

        # Remover colunas temporárias se existirem
        df.drop(columns=["DataLimpa", "DataFormatada"], errors="ignore", inplace=True)

        # Validação flexível: aceita ocorrências de Auditoria E de Ocorrências
        from app.processamento.motivos_ocorrencias import validar_motivo

        def eh_registro_valido(row):
            ocorr = row.get("Ocorrência")
            if isinstance(ocorr, str) and (validar_ocorrencia(ocorr.strip()) or "interjornada" in ocorr.lower()):
                return True
            motivo = row.get("Motivo")
            if isinstance(motivo, str) and validar_motivo(motivo.strip()):
                return True
            if isinstance(ocorr, str) and validar_motivo(ocorr.strip()):
                return True
            return False

        df = df[df.apply(eh_registro_valido, axis=1)]

        return df
    elif tipo_relatorio == "Ocorrências":
        return carregar_dados_ocorrencias(caminho_csv)
    elif tipo_relatorio == "Assinaturas":
        return carregar_dados_assinaturas(caminho_csv)
    else:
        raise ValueError("Tipo de relatório inválido. Escolha 'Auditoria', 'Ocorrências' ou 'Assinaturas'.")


