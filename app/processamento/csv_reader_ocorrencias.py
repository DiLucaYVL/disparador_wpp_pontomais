import pandas as pd
from app.processamento.mapear_gerencia import mapear_equipe
from app.processamento.motivos_ocorrencias import validar_motivo, validar_acao_pendente
from app.whatsapp.mensagem import validar_ocorrencia

def carregar_dados_ocorrencias(caminho_csv):
    """
    Carrega dados do relatório de ocorrências.
    Suporta detecção dinâmica de cabeçalho e rodapé (Resumo/Total).
    Colunas esperadas: Nome, Equipe, Data, e Motivo e/ou Ocorrência.
    """
    with open(caminho_csv, encoding="utf-8", errors="replace") as _f:
        _linhas = _f.readlines()
    _total_linhas = len(_linhas)

    _linha_cabecalho = next(
        (
            i for i, l in enumerate(_linhas)
            if l.strip().startswith("Nome,")
            or ("Nome" in l and "Equipe" in l and ("Motivo" in l or "Ação pendente" in l or "Ocorrência" in l or "Ocorr" in l))
        ),
        None,
    )
    _skiprows = _linha_cabecalho if _linha_cabecalho is not None else 4

    _linha_resumo = next(
        (i for i, l in enumerate(_linhas) if i > _skiprows and (l.strip().startswith("Resumo") or l.strip().startswith("Total"))),
        None,
    )
    _skipfooter = (
        _total_linhas - _linha_resumo
        if _linha_resumo is not None
        else (0 if _linha_cabecalho == 0 else 5)
    )

    df = pd.read_csv(caminho_csv, skiprows=_skiprows, skipfooter=_skipfooter, engine="python")

    # Limpar nomes de colunas
    df.columns = df.columns.str.strip()

    # Verificar se as colunas mínimas existem
    colunas_obrigatorias = ['Nome', 'Equipe', 'Data']
    colunas_faltantes = [col for col in colunas_obrigatorias if col not in df.columns]
    if colunas_faltantes:
        raise ValueError(f"Colunas faltantes no arquivo CSV: {colunas_faltantes}")

    if 'Motivo' not in df.columns and 'Ocorrência' not in df.columns:
        raise ValueError("Colunas faltantes no arquivo CSV: 'Motivo' ou 'Ocorrência'")

    # Se uma coluna existe e a outra não, replica para garantir compatibilidade
    if 'Motivo' not in df.columns and 'Ocorrência' in df.columns:
        df['Motivo'] = df['Ocorrência']
    if 'Ocorrência' not in df.columns and 'Motivo' in df.columns:
        df['Ocorrência'] = df['Motivo']

    if 'Ação pendente' not in df.columns:
        df['Ação pendente'] = ""

    # Limpar dados
    df['Data'] = df['Data'].astype(str).str.replace('"', '').str.split(',').str[-1].str.strip()
    df['Nome'] = df['Nome'].astype(str).str.strip()
    df['Motivo'] = df['Motivo'].astype(str).str.strip()
    df['Ação pendente'] = df['Ação pendente'].astype(str).str.strip()
    if 'Ocorrência' in df.columns:
        df['Ocorrência'] = df['Ocorrência'].astype(str).str.strip()
        mascara_inter = df['Ocorrência'].str.contains('interjornada', case=False, na=False)
        df.loc[mascara_inter, 'Ocorrência'] = 'Interjornada insuficiente'

    # Mapear equipes
    df['EquipeTratada'] = df['Equipe'].apply(mapear_equipe)

    # Remover linhas vazias nas colunas identificadoras
    df = df.dropna(subset=['Nome', 'Data'])

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

