import requests
import json
import logging
import time
import random
import os

config_path = os.path.join(os.path.dirname(__file__), "..", "..", "static", "config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

EVOLUTION_URL = config["EVOLUTION_URL"]
EVOLUTION_INSTANCE = config["EVOLUTION_INSTANCE"]
EVOLUTION_TOKEN = config.get("EVOLUTION_TOKEN", "")

def _get_headers():
    """Retorna os headers padrão para as requisições"""
    return {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_TOKEN
    }

def enviar_whatsapp(numero, mensagem, equipe=None):
    numero_formatado = numero.replace("+", "").replace("-", "").replace(" ", "")
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    
    payload = {
        "number": numero_formatado,
        "text": mensagem,
        "delay": 50                # Delay antes do envio (ms)
    }

    try:
        logging.info(f"⏳ Enviando para {numero_formatado} (Equipe: {equipe})")
        logging.info(f"Payload: {payload}")

        # Envia diretamente com delay e presence no payload
        response = requests.post(url, json=payload, headers=_get_headers())

        logging.info(f"Evolution API status: {response.status_code}")
        logging.info(f"Evolution API response: {response.text}")

        if response.status_code not in [200, 201]:
            raise Exception(f"Erro Evolution API: {response.status_code} - {response.text}")

        response_data = response.json()
        if not response_data.get("success", True):
            raise Exception(f"Erro na resposta: {response_data.get('message', 'Erro desconhecido')}")

        logging.info(f"✅ Mensagem enviada para {numero_formatado} (Equipe: {equipe})")
        time.sleep(random.uniform(4, 8))

    except Exception as e:
        logging.error(f"❌ Falha ao enviar para {numero_formatado} - {e}")
        raise