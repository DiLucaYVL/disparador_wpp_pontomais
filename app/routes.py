from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
import logging
import uuid
import random
import time
import requests
from urllib.parse import urljoin
from app.processamento.mapear_gerencia import mapear_equipe
from app.processamento.csv_reader import carregar_dados
from app.config.settings import (
    EVOLUTION_INSTANCE,
    EVOLUTION_TOKEN,
    EVOLUTION_URL,
)

api_bp = Blueprint('api', __name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _evo_headers():
    return {"Content-Type": "application/json", "apikey": EVOLUTION_TOKEN}


def verificar_sessao() -> bool:
    """Garante que a sessão do WhatsApp esteja ativa."""
    url = urljoin(
        EVOLUTION_URL,
        f"/instance/fetchInstances?instanceName={EVOLUTION_INSTANCE}",
    )
    try:
        resp = requests.get(url, headers=_evo_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        estado = (
            data.get("state")
            or data.get("connectionState")
            or data.get("instance", {}).get("state")
        )
        if isinstance(estado, str) and estado.lower() == "open":
            return True
    except Exception as exc:  # noqa: BLE001
        logging.error("Erro ao verificar instâncias: %s", exc)

    url = urljoin(EVOLUTION_URL, f"/instance/connect/{EVOLUTION_INSTANCE}")
    try:
        resp = requests.get(url, headers=_evo_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        estado = (
            data.get("state")
            or data.get("connectionState")
            or data.get("instance", {}).get("state")
        )
        return isinstance(estado, str) and estado.lower() == "open"
    except Exception as exc:  # noqa: BLE001
        logging.error("Erro ao conectar instância: %s", exc)
        return False


def enviar_whatsapp(numero, mensagem, equipe=None):
    if not verificar_sessao():
        logging.error("Sessão do WhatsApp desconectada")
        raise RuntimeError("Sessão do WhatsApp desconectada")

    numero_formatado = numero.replace("+", "").replace("-", "").replace(" ", "")
    url = urljoin(EVOLUTION_URL, f"/message/sendText/{EVOLUTION_INSTANCE}")

    payload = {
        "number": numero_formatado,
        "text": mensagem,
        "delay": 250,
    }

    try:
        logging.info("⏳ Enviando para %s (Equipe: %s)", numero_formatado, equipe)
        logging.info("Payload: %s", payload)

        response = requests.post(
            url, json=payload, headers=_evo_headers(), timeout=30
        )

        logging.info("Evolution API status: %s", response.status_code)
        logging.info("Evolution API response: %s", response.text)

        if 400 <= response.status_code < 500:
            req = response.request
            logging.error(
                "Falha 4xx ao chamar Evolution API - endpoint=%s método=%s body=%s",
                req.url,
                req.method,
                req.body,
            )

        if response.status_code not in [200, 201]:
            raise Exception(
                f"Erro Evolution API: {response.status_code} - {response.text}"
            )

        response_data = response.json()
        if not response_data.get("success", True):
            raise Exception(
                f"Erro na resposta: {response_data.get('message', 'Erro desconhecido')}"
            )

        logging.info(
            "✅ Mensagem enviada para %s (Equipe: %s)", numero_formatado, equipe
        )

        time.sleep(random.uniform(0.25, 0.5))

    except SystemExit as se:
        logging.error(
            "🚨 SYSTEMEXIT CAPTURADO - Worker sendo morto pelo Gunicorn!"
        )
        logging.error("🚨 Exit code: %s", se.code)
        raise
    except Exception as e:  # noqa: BLE001
        logging.error("❌ Falha ao enviar para %s - %s", numero_formatado, e)
        raise
    except BaseException as be:  # noqa: BLE001
        logging.error("🚨 BASEEXCEPTION CAPTURADA: %s", type(be).__name__)
        raise


@api_bp.route('/config', methods=['GET'])
def get_config():
    return jsonify({
        "EVOLUTION_URL": EVOLUTION_URL,
        "EVOLUTION_INSTANCE": EVOLUTION_INSTANCE,
    })

@api_bp.route('/enviar', methods=['POST'])
def enviar():
    from app.tasks import enqueue_csv_processing
    try:
        file = request.files.get('csvFile')
        ignorar_sabados = request.form.get('ignorarSabados', 'true') == 'true'
        tipo_relatorio = request.form.get('tipoRelatorio', 'Auditoria').strip()
        if tipo_relatorio not in {"Auditoria", "Ocorrências", "Assinaturas"}:
            return jsonify({
                "success": False,
                "log": [{"type": "error", "message": f"❌ Tipo de relatório inválido: {tipo_relatorio}. Selecione 'Auditoria', 'Ocorrências' ou 'Assinaturas'."}]
            }), 400

        debug_mode = request.form.get('debugMode', 'false') == 'true'

        if not file:
            return jsonify({"success": False, "log": ["❌ Nenhum arquivo CSV enviado."]}), 400

        if not file.filename.lower().endswith('csv'):
            return jsonify({"success": False, "log": ["❌ Formato inválido. Envie um arquivo .csv"]}), 400

        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex[:8]}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        equipes_selecionadas = request.form.get('equipesSelecionadas')
        equipes_selecionadas = set(json.loads(equipes_selecionadas)) if equipes_selecionadas else None

        task_id = enqueue_csv_processing(
            filepath, ignorar_sabados, tipo_relatorio, equipes_selecionadas, debug_mode
        )

        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "Processamento agendado"
        }), 202

    except Exception as e:  # noqa: BLE001
        logging.exception("Erro ao agendar processamento.")
        return jsonify({
            "success": False,
            "log": [{"type": "error", "message": "❌ Erro ao agendar processamento."}]
        }), 500


@api_bp.route('/status/<task_id>', methods=['GET'])
def status(task_id):
    """Retorna o andamento e o resultado de uma tarefa agendada."""
    from app.tasks import get_task_status

    task = get_task_status(task_id)
    if not task:
        return jsonify({"success": False, "error": "Tarefa não encontrada"}), 404

    if task["status"] == "done":
        result = task["result"]
        return jsonify({
            "success": True,
            "status": "done",
            "log": result["logs"],
            "stats": result["stats"],
            "debug": result.get("debug"),
            "nome_arquivo_log": result.get("nome_arquivo_log"),
        })

    if task["status"] == "error":
        return jsonify({
            "success": False,
            "status": "error",
            "error": task["error"],
        })

    return jsonify({"success": True, "status": task["status"]})


@api_bp.route('/equipes', methods=['POST'])
def obter_equipes():
    file = request.files.get('csvFile')
    ignorar_sabados = request.form.get('ignorarSabados', 'true') == 'true'
    tipo_relatorio = request.form.get('tipoRelatorio', 'Auditoria')
    if tipo_relatorio not in {"Auditoria", "Ocorrências", "Assinaturas"}:
        return jsonify({
            "success": False,
            "error": f"Tipo de relatório inválido: {tipo_relatorio}"
        }), 400

    if not file or not file.filename.lower().endswith('csv'):
        return jsonify({"success": False, "error": "Arquivo CSV inválido"}), 400

    filename = secure_filename(file.filename)
    filename = f"{uuid.uuid4().hex[:8]}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        df = carregar_dados(filepath, ignorar_sabados, tipo_relatorio)

        df['EquipeTratada'] = df['Equipe'].apply(mapear_equipe)

        equipes = sorted(df['EquipeTratada'].dropna().unique().tolist())
        logging.info(f"Equipes extraídas: {len(equipes)}")

        return jsonify({"success": True, "equipes": equipes})
    
    except Exception as e:
        logging.exception("Erro ao processar CSV para extração de equipes.")
        return jsonify({"success": False, "error": str(e)}), 500
    
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

@api_bp.route('/.well-known/<path:subpath>')
def well_known(subpath):
    # Não serve nada; só evita poluir o log com 404
    return ("", 204)


@api_bp.route('/whatsapp/status', methods=['GET'])
def whatsapp_status():
    try:
        url = urljoin(EVOLUTION_URL, f"/instance/connectionState/{EVOLUTION_INSTANCE}")
        resp = requests.get(url, headers=_evo_headers(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as exc:  # noqa: BLE001
        logging.exception("Erro ao obter status do WhatsApp")
        return jsonify({"error": str(exc)}), 500


@api_bp.route('/whatsapp/qr', methods=['GET'])
def whatsapp_qr():
    try:
        url = urljoin(EVOLUTION_URL, f"/instance/connect/{EVOLUTION_INSTANCE}")
        resp = requests.get(url, headers=_evo_headers(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as exc:  # noqa: BLE001
        logging.exception("Erro ao obter QR Code do WhatsApp")
        return jsonify({"error": str(exc)}), 500


@api_bp.route('/whatsapp/instance', methods=['GET'])
def whatsapp_instance():
    try:
        url = urljoin(
            EVOLUTION_URL,
            f"/instance/fetchInstances?instanceName={EVOLUTION_INSTANCE}",
        )
        resp = requests.get(url, headers=_evo_headers(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as exc:  # noqa: BLE001
        logging.exception("Erro ao obter dados da instância")
        return jsonify({"error": str(exc)}), 500


@api_bp.route('/whatsapp/logout', methods=['DELETE'])
def whatsapp_logout():
    try:
        url = urljoin(EVOLUTION_URL, f"/instance/logout/{EVOLUTION_INSTANCE}")
        resp = requests.delete(url, headers=_evo_headers(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as exc:  # noqa: BLE001
        logging.exception("Erro ao desconectar WhatsApp")
        return jsonify({"error": str(exc)}), 500
