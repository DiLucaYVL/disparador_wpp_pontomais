import logging
import random
import signal
import sys
import time

import requests
from app.config.settings import (
    EVOLUTION_INSTANCE,
    EVOLUTION_TOKEN,
    EVOLUTION_URL,
)

def _get_headers():
    """Retorna os headers padrão para as requisições"""
    return {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_TOKEN
    }

def signal_handler(signum, frame):
    """Loga sinais recebidos do sistema e finaliza o processo."""
    logging.error(f"🚨 SINAL RECEBIDO: {signum} - Worker sendo morto pelo Gunicorn")
    sys.exit(1)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGABRT, signal_handler)


def enviar_whatsapp(numero, mensagem, equipe=None):
    numero_formatado = numero.replace("+", "").replace("-", "").replace(" ", "")
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"

    payload = {
        "number": numero_formatado,
        "text": mensagem,
        "delay": 250,  # Delay antes do envio (ms
    }

    try:
        logging.info(f"⏳ Enviando para {numero_formatado} (Equipe: {equipe})")
        logging.info(f"Payload: {payload}")

        response = requests.post(
            url, json=payload, headers=_get_headers(), timeout=30
        )

        logging.info(f"Evolution API status: {response.status_code}")
        logging.info(f"Evolution API response: {response.text}")

        if response.status_code not in [200, 201]:
            raise Exception(
                f"Erro Evolution API: {response.status_code} - {response.text}"
            )

        response_data = response.json()
        if not response_data.get("success", True):
            raise Exception(
                f"Erro na resposta: {response_data.get('message', 'Erro desconhecido')}"
            )

        logging.info(f"✅ Mensagem enviada para {numero_formatado} (Equipe: {equipe})")

        time.sleep(random.uniform(0.25, 0.5))


    except SystemExit as se:
        logging.error(
            "🚨 SYSTEMEXIT CAPTURADO - Worker sendo morto pelo Gunicorn!"
        )
        logging.error(f"🚨 Exit code: {se.code}")
        raise
    except BaseException as be:
        logging.error(f"🚨 BASEEXCEPTION CAPTURADA: {type(be).__name__}")
        raise
    except Exception as e:
        logging.error(f"❌ Falha ao enviar para {numero_formatado} - {e}")
        raise