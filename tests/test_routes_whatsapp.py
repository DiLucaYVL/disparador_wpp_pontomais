import pytest
from unittest.mock import patch, MagicMock
from app.routes import _extrair_estado, verificar_sessao
from main import app


def test_extrair_estado_from_dict_instance_state():
    data = {
        "instance": {
            "instanceName": "instancia_teste",
            "state": "open"
        }
    }
    assert _extrair_estado(data, "instancia_teste") == "open"


def test_extrair_estado_from_dict_flat_state():
    data = {
        "instanceName": "instancia_teste",
        "state": "close"
    }
    assert _extrair_estado(data, "instancia_teste") == "close"


def test_extrair_estado_from_list_fetch_instances():
    data = [
        {
            "instance": {
                "instanceName": "instancia_teste",
                "status": "open",
                "profileName": "Empresa XPTO"
            }
        }
    ]
    assert _extrair_estado(data, "instancia_teste") == "open"


def test_extrair_estado_from_connection_status_nested():
    data = {
        "instance": {
            "instanceName": "instancia_teste",
            "connectionStatus": {
                "state": "connecting"
            }
        }
    }
    assert _extrair_estado(data, "instancia_teste") == "connecting"


def test_extrair_estado_empty_or_none():
    assert _extrair_estado(None, "instancia_teste") is None
    assert _extrair_estado({}, "instancia_teste") is None
    assert _extrair_estado([], "instancia_teste") is None


@patch("app.routes.requests.get")
def test_verificar_sessao_open(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "instance": {
            "instanceName": "topfama",
            "state": "open"
        }
    }
    mock_get.return_value = mock_resp

    with patch("app.routes.EVOLUTION_INSTANCE", "topfama"):
        conectado, estado = verificar_sessao()
        assert conectado is True
        assert estado == "open"


@patch("app.routes.requests.get")
def test_verificar_sessao_connecting(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "instance": {
            "instanceName": "topfama",
            "state": "connecting"
        }
    }
    mock_get.return_value = mock_resp

    with patch("app.routes.EVOLUTION_INSTANCE", "topfama"):
        conectado, estado = verificar_sessao()
        assert conectado is False
        assert estado == "connecting"


def test_whatsapp_status_endpoint():
    client = app.test_client()
    with patch("app.routes.verificar_sessao", return_value=(True, "open")):
        res = client.get("/whatsapp/status")
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data["success"] is True
        assert json_data["connected"] is True
        assert json_data["status"] == "open"
        assert json_data["state"] == "open"
