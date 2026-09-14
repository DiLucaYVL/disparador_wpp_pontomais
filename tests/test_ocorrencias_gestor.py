import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from app.processamento.motivos_ocorrencias import eh_pendencia_gestor, ACAO_PENDENTE_GESTOR
from app.processamento.ocorrencias_processor import filtrar_pendencia_gestor
from app.history import buscar_ocorrencias_enviadas


def _df_ocorrencias():
    return pd.DataFrame([
        {
            "Nome": "Maria Silva",
            "Equipe": "Loja 75",
            "Data": "11/11/2025",
            "Motivo": "Número errado de pontos",
            "Ação pendente": "Gestor aprovar solicitação de ajuste",
        },
        {
            "Nome": "Joao Souza",
            "Equipe": "Loja 75",
            "Data": "12/11/2025",
            "Motivo": "Número errado de pontos",
            "Ação pendente": "Colaborador solicitar ajuste",
        },
        {
            "Nome": "Ana Pereira",
            "Equipe": "Loja 75",
            "Data": "13/11/2025",
            "Motivo": "Número de pontos menor que o previsto",
            "Ação pendente": "Gestor corrigir lançamento de exceção",
        },
    ])


def test_eh_pendencia_gestor():
    assert eh_pendencia_gestor("Gestor aprovar solicitação de ajuste") is True
    assert eh_pendencia_gestor(" Gestor aprovar solicitação de ajuste ") is True
    assert eh_pendencia_gestor("Colaborador solicitar ajuste") is False
    assert eh_pendencia_gestor("Gestor corrigir lançamento de exceção") is False
    assert eh_pendencia_gestor("") is False


def test_filtrar_pendencia_gestor_mantem_apenas_gestor_aprovar():
    df = _df_ocorrencias()
    filtrado = filtrar_pendencia_gestor(df)

    assert len(filtrado) == 1
    assert filtrado.iloc[0]["Nome"] == "Maria Silva"
    assert filtrado.iloc[0]["Ação pendente"] == ACAO_PENDENTE_GESTOR


def test_filtrar_pendencia_gestor_df_vazio():
    df = pd.DataFrame(columns=["Nome", "Ação pendente"])
    filtrado = filtrar_pendencia_gestor(df)
    assert filtrado.empty


def test_filtrar_pendencia_gestor_sem_coluna_retorna_df_original():
    df = pd.DataFrame([{"Nome": "Maria"}])
    filtrado = filtrar_pendencia_gestor(df)
    assert filtrado.equals(df)


@patch("app.history.get_connection")
@patch("app.history.init_db")
def test_buscar_ocorrencias_enviadas_retorna_apenas_intersecao(mock_init_db, mock_get_connection):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("Maria Silva", "Número errado de pontos", "11/11/2025"),
        ("Outra Pessoa", "Motivo qualquer", "01/01/2025"),
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_connection.return_value.__enter__.return_value = mock_conn

    candidatos = [
        ("Maria Silva", "Número errado de pontos", "11/11/2025"),
        ("Joao Souza", "Número errado de pontos", "12/11/2025"),
    ]

    resultado = buscar_ocorrencias_enviadas("Ocorrências", candidatos)

    assert resultado == {("Maria Silva", "Número errado de pontos", "11/11/2025")}
    mock_init_db.assert_called_once()


@patch("app.history.get_connection")
@patch("app.history.init_db")
def test_buscar_ocorrencias_enviadas_sem_candidatos_nao_consulta_banco(mock_init_db, mock_get_connection):
    resultado = buscar_ocorrencias_enviadas("Ocorrências", [])
    assert resultado == set()
    mock_init_db.assert_not_called()
    mock_get_connection.assert_not_called()
