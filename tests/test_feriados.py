from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from app.services import feriados
from app.services.feriados import (
    buscar_feriados_ano,
    calcular_feriados_locais,
    calcular_pascoa,
    gerar_rodape_feriados,
    identificar_feriados,
    listar_feriados_df,
    remover_datas_feriado,
)

RESPOSTA_2025 = [
    {"date": "2025-11-15", "name": "Proclamação da República", "type": "national"},
    {"date": "2025-11-20", "name": "Dia da consciência negra", "type": "national"},
    {"date": "2025-12-25", "name": "Natal", "type": "national"},
]


@pytest.fixture(autouse=True)
def limpar_cache():
    feriados._cache_feriados.clear()
    yield
    feriados._cache_feriados.clear()


def _mock_resposta(dados):
    resp = MagicMock()
    resp.json.return_value = dados
    resp.raise_for_status.return_value = None
    return resp


def test_buscar_feriados_ano_converte_datas_e_usa_cache():
    with patch("app.services.feriados.requests.get", return_value=_mock_resposta(RESPOSTA_2025)) as mock_get:
        resultado = buscar_feriados_ano(2025)
        buscar_feriados_ano(2025)

    assert resultado["20/11/2025"] == "Dia da consciência negra"
    assert resultado["25/12/2025"] == "Natal"
    mock_get.assert_called_once()


RESPOSTA_NAGER_2025 = [
    {"date": "2025-07-09", "localName": "Revolução Constitucionalista de 1932", "global": False},
    {"date": "2025-11-20", "localName": "Dia da Consciência Negra", "global": True},
]


def test_buscar_feriados_ano_usa_nager_quando_brasilapi_falha():
    def fake_get(url, timeout):
        if "brasilapi" in url:
            raise requests.ConnectionError("offline")
        return _mock_resposta(RESPOSTA_NAGER_2025)

    with patch("app.services.feriados.requests.get", side_effect=fake_get):
        resultado = buscar_feriados_ano(2025)

    # Feriados estaduais (global=False) não entram.
    assert resultado == {"20/11/2025": "Dia da Consciência Negra"}


def test_buscar_feriados_ano_usa_calculo_local_quando_apis_falham():
    with patch("app.services.feriados.requests.get", side_effect=requests.ConnectionError("offline")):
        resultado = buscar_feriados_ano(2025)

    assert resultado == calcular_feriados_locais(2025)
    assert 2025 in feriados._cache_feriados


def test_calcular_feriados_locais_igual_brasilapi_2025():
    esperado = [
        "01/01/2025", "03/03/2025", "04/03/2025", "18/04/2025", "20/04/2025",
        "21/04/2025", "01/05/2025", "19/06/2025", "07/09/2025", "12/10/2025",
        "02/11/2025", "15/11/2025", "20/11/2025", "25/12/2025",
    ]
    assert list(calcular_feriados_locais(2025)) == esperado


def test_calcular_feriados_locais_consciencia_negra_a_partir_de_2024():
    assert "20/11/2023" not in calcular_feriados_locais(2023)
    assert "20/11/2024" in calcular_feriados_locais(2024)


@pytest.mark.parametrize("ano, pascoa", [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5))])
def test_calcular_pascoa(ano, pascoa):
    assert calcular_pascoa(ano) == pascoa


def test_identificar_feriados_filtra_datas_presentes():
    with patch("app.services.feriados.requests.get", return_value=_mock_resposta(RESPOSTA_2025)):
        resultado = identificar_feriados(["20/11/2025", "19/11/2025", "15/11/2025", "invalida", "20/11/2025"])

    assert list(resultado.items()) == [
        ("15/11/2025", "Proclamação da República"),
        ("20/11/2025", "Dia da consciência negra"),
    ]


def test_listar_feriados_df_e_remover_datas():
    df = pd.DataFrame([
        {"Nome": "Ana", "Data": "19/11/2025"},
        {"Nome": "Ana", "Data": "20/11/2025"},
    ])
    with patch("app.services.feriados.requests.get", return_value=_mock_resposta(RESPOSTA_2025)):
        lista = listar_feriados_df(df)

    assert lista == [{"data": "20/11/2025", "nome": "Dia da consciência negra"}]

    filtrado = remover_datas_feriado(df, {"20/11/2025": "Dia da consciência negra"})
    assert filtrado["Data"].tolist() == ["19/11/2025"]


def test_gerar_rodape_feriados_em_italico():
    rodape = gerar_rodape_feriados()

    assert rodape.startswith("_") and rodape.endswith("_")
    assert "estadual ou municipal" in rodape


def _df_ocorrencias_feriado():
    return pd.DataFrame([
        {
            "Nome": "Maria Silva",
            "Equipe": "Loja 75",
            "EquipeTratada": "75",
            "Data": "19/11/2025",
            "Motivo": "Número errado de pontos",
            "Ocorrência": "Número errado de pontos",
            "Ação pendente": "Gestor aprovar solicitação de ajuste",
        },
        {
            "Nome": "Maria Silva",
            "Equipe": "Loja 75",
            "EquipeTratada": "75",
            "Data": "20/11/2025",
            "Motivo": "Número errado de pontos",
            "Ocorrência": "Número errado de pontos",
            "Ação pendente": "Gestor aprovar solicitação de ajuste",
        },
    ])


def _executar_controller(incluir_feriados, df=None):
    from app import controller

    df = _df_ocorrencias_feriado() if df is None else df
    with patch.object(controller, "carregar_dados", return_value=df), \
            patch.object(controller, "carregar_numeros_equipes", return_value={"75": "5511999999999"}), \
            patch.object(controller, "enviar_whatsapp") as mock_enviar, \
            patch.object(controller, "buscar_ocorrencias_enviadas", return_value=set()), \
            patch.object(controller, "registrar_envio"), \
            patch.object(controller, "registrar_resultado_relatorio"), \
            patch.object(controller, "registrar_dataframe_no_sheets"), \
            patch.object(controller, "configurar_log", return_value="log.txt"), \
            patch("app.services.feriados.requests.get", return_value=_mock_resposta(RESPOSTA_2025)):
        _, stats, _ = controller.processar_csv(
            "arquivo.csv",
            True,
            "Ocorrências",
            nome_relatorio="relatorio",
            incluir_feriados=incluir_feriados,
        )
    return mock_enviar, stats


def test_controller_inclui_feriado_sem_rodape():
    mock_enviar, stats = _executar_controller(incluir_feriados=True)

    mensagem = mock_enviar.call_args[0][1]
    assert "NO DIA 20/11/2025" in mensagem
    assert "_Obs.:" not in mensagem
    assert stats["ignoradas_feriado"] == 0


def test_controller_remove_feriado_com_rodape():
    mock_enviar, stats = _executar_controller(incluir_feriados=False)

    mensagem = mock_enviar.call_args[0][1]
    assert "NO DIA 19/11/2025" in mensagem
    assert "20/11/2025" not in mensagem
    assert mensagem.endswith(gerar_rodape_feriados())
    assert stats["ignoradas_feriado"] == 1


def test_controller_sem_feriados_detectados_envia_com_rodape():
    df = _df_ocorrencias_feriado().iloc[[0]]
    mock_enviar, stats = _executar_controller(incluir_feriados=True, df=df)

    mensagem = mock_enviar.call_args[0][1]
    assert "NO DIA 19/11/2025" in mensagem
    assert mensagem.endswith(gerar_rodape_feriados())
    assert stats["ignoradas_feriado"] == 0
