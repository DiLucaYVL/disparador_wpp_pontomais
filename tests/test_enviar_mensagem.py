import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.abspath("."))

from app.whatsapp.enviar_mensagem import enviar_whatsapp


@patch("app.whatsapp.enviar_mensagem.requests.post")
@patch("app.whatsapp.enviar_mensagem.requests.get")
def test_enviar_whatsapp_sessao_aberta(mock_get, mock_post):
    """Deve enviar mensagem quando a sessão estiver aberta."""
    resp_get = MagicMock(status_code=200)
    resp_get.json.return_value = {"connectionState": "open"}
    mock_get.return_value = resp_get

    resp_post = MagicMock(status_code=200, text="OK")
    resp_post.json.return_value = {"success": True}
    mock_post.return_value = resp_post

    enviar_whatsapp("+5511999999999", "Olá", "Equipe")

    mock_get.assert_called_once()
    mock_post.assert_called_once()


@patch("app.whatsapp.enviar_mensagem.requests.post")
@patch("app.whatsapp.enviar_mensagem.requests.get")
def test_enviar_whatsapp_sessao_fechada(mock_get, mock_post):
    """Deve lançar erro e não enviar mensagem se a sessão estiver fechada."""
    resp_get = MagicMock(status_code=200)
    resp_get.json.return_value = {"connectionState": "close"}
    mock_get.return_value = resp_get

    with pytest.raises(RuntimeError, match="Sessão do WhatsApp desconectada"):
        enviar_whatsapp("+5511999999999", "Olá")

    mock_get.assert_called_once()
    mock_post.assert_not_called()
