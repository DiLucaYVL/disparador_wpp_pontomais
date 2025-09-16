"""Gera resumos matriciais com suporte a drill-down por pessoa."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


_COLUNA_MOTIVO_POR_TIPO: Dict[str, str] = {
    "Auditoria": "Ocorrência",
    "Ocorrências": "Motivo",
    "Assinaturas": "Período (Fechamento)",
}


def _normalizar_texto(valor: Any, padrao: str) -> str:
    """Converte valores vazios em um texto padrão legível."""
    if pd.isna(valor):
        return padrao
    texto = str(valor).strip()
    return texto or padrao


def gerar_resumo_matricial(df: pd.DataFrame, tipo_relatorio: str) -> List[Dict[str, Any]]:
    """Cria um resumo matricial com drill-down por pessoa.

    Retorna uma lista de dicionários com a estrutura::

        {
            "equipe": "Equipe",
            "tipo_relatorio": "Auditoria",
            "motivo": "Falta",
            "qtd": 5,
            "detalhes": [{"nome": "Maria", "qtd": 2}, ...]
        }

    O objetivo é alimentar a visualização interativa na interface, permitindo
    explorar o total consolidado e os detalhes por pessoa (drill-down).
    """
    if df is None or df.empty:
        return []

    coluna_motivo = _COLUNA_MOTIVO_POR_TIPO.get(tipo_relatorio)
    if not coluna_motivo or coluna_motivo not in df.columns:
        return []

    df_tratado = df.copy()

    if "EquipeTratada" in df_tratado.columns:
        equipe_base = df_tratado["EquipeTratada"]
    elif "Equipe" in df_tratado.columns:
        equipe_base = df_tratado["Equipe"]
    else:
        equipe_base = pd.Series([None] * len(df_tratado), index=df_tratado.index)

    df_tratado["EquipeResumo"] = equipe_base.apply(
        lambda valor: _normalizar_texto(valor, "Equipe não informada")
    )

    if "Nome" in df_tratado.columns:
        pessoa_base = df_tratado["Nome"]
    else:
        pessoa_base = pd.Series([None] * len(df_tratado), index=df_tratado.index)

    df_tratado["PessoaResumo"] = pessoa_base.apply(
        lambda valor: _normalizar_texto(valor, "Colaborador não informado")
    )

    df_tratado["MotivoResumo"] = df_tratado[coluna_motivo].apply(
        lambda valor: _normalizar_texto(valor, "Motivo não informado")
    )

    resumo: List[Dict[str, Any]] = []
    grupos = df_tratado.groupby(["EquipeResumo", "MotivoResumo"], dropna=False)

    for (equipe, motivo), grupo in grupos:
        total = int(grupo.shape[0])
        detalhes_df = (
            grupo.groupby("PessoaResumo", dropna=False)
            .size()
            .reset_index(name="Quantidade")
            .sort_values(by=["Quantidade", "PessoaResumo"], ascending=[False, True])
        )

        detalhes = [
            {"nome": str(row["PessoaResumo"]), "qtd": int(row["Quantidade"])}
            for _, row in detalhes_df.iterrows()
        ]

        resumo.append({
            "equipe": str(equipe),
            "tipo_relatorio": tipo_relatorio,
            "motivo": str(motivo),
            "qtd": total,
            "detalhes": detalhes,
        })

    resumo.sort(key=lambda item: (item["equipe"], item["motivo"]))
    return resumo
