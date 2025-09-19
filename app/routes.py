from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import json
import logging
import uuid
import random
import time
from datetime import datetime
import requests
from urllib.parse import urljoin
from app.processamento.mapear_gerencia import mapear_equipe
from app.processamento.csv_reader import carregar_dados
from app.config.settings import (
    EVOLUTION_INSTANCE,
    EVOLUTION_TOKEN,
    EVOLUTION_URL,
)
from app.history import (
    listar_envios,
    listar_equipes_disponiveis,
    normalizar_nome_relatorio,
    obter_status_relatorio,
    STATUS_SUCESSO_TOTAL,
    STATUS_ENVIO_PARCIAL,
)
from app.history_export import gerar_planilha_historico

api_bp = Blueprint('api', __name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _evo_headers():
    return {"Content-Type": "application/json", "apikey": EVOLUTION_TOKEN}


def verificar_sessao() -> bool:
    """Garante que a sessão do WhatsApp esteja ativa.

    A Evolution pode retornar lista de instâncias ou um objeto.
    Esta função trata ambos para evitar erros do tipo 'list' não possui 'get'.
    """
    url = urljoin(
        EVOLUTION_URL,
        f"/instance/fetchInstances?instanceName={EVOLUTION_INSTANCE}",
    )
    try:
        resp = requests.get(url, headers=_evo_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()

        estado = None
        if isinstance(data, list):
            try:
                alvo = next(
                    (
                        item for item in data
                        if isinstance(item, dict)
                        and (
                            item.get("instanceName") == EVOLUTION_INSTANCE
                            or item.get("instance", {}).get("instanceName") == EVOLUTION_INSTANCE
                        )
                    ),
                    data[0] if data else {},
                )
            except Exception:  # noqa: BLE001
                alvo = {}
            if isinstance(alvo, dict):
                estado = (
                    alvo.get("state")
                    or alvo.get("connectionState")
                    or alvo.get("instance", {}).get("state")
                )
        elif isinstance(data, dict):
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
        estado = None
        if isinstance(data, dict):
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
                "log": [{"type": "error", "message": f"⚠️ Tipo de relatório inválido: {tipo_relatorio}. Selecione 'Auditoria', 'Ocorrências' ou 'Assinaturas'."}]
            }), 400

        debug_mode = request.form.get('debugMode', 'false') == 'true'
        forcar_reenvio = request.form.get('forcarReenvio', 'false').lower() == 'true'

        if not file:
            return jsonify({"success": False, "log": ["⚠️ Nenhum arquivo CSV enviado."]}), 400

        if not file.filename.lower().endswith('csv'):
            return jsonify({"success": False, "log": ["⚠️ Formato inválido. Envie um arquivo .csv"]}), 400

        nome_relatorio_original = (file.filename or '').strip()
        nome_relatorio_normalizado = normalizar_nome_relatorio(nome_relatorio_original)
        if not nome_relatorio_normalizado:
            return jsonify({
                "success": False,
                "log": [{"type": "error", "message": "⚠️ Não foi possível identificar o nome do relatório enviado."}]
            }), 400

        status_relatorio = obter_status_relatorio(nome_relatorio_original)
        equipes_permitidas = None
        if status_relatorio:
            status_atual = (status_relatorio.get('status') or '').strip()
            if status_atual == STATUS_SUCESSO_TOTAL and not forcar_reenvio:
                return jsonify({
                    "success": False,
                    "code": "relatorio_concluido",
                    "message": "Esse relatório já foi enviado anteriormente. Se você refizer o envio, poderá enviar mensagens que já foram enviadas antes."
                }), 409
            if status_atual == STATUS_ENVIO_PARCIAL:
                pendencias = status_relatorio.get('pendencias') or []
                equipes_permitidas = {str(item).strip() for item in pendencias if str(item).strip()}
                if not equipes_permitidas:
                    return jsonify({
                        "success": False,
                        "code": "relatorio_sem_pendencias",
                        "message": "Não há pendências para esse relatório. Todas as mensagens já foram registradas."
                    }), 409

        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex[:8]}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        equipes_selecionadas_raw = request.form.get('equipesSelecionadas')
        equipes_selecionadas = None
        if equipes_selecionadas_raw:
            try:
                selecionadas_lista = json.loads(equipes_selecionadas_raw)
            except json.JSONDecodeError:
                return jsonify({
                    "success": False,
                    "log": [{"type": "error", "message": "⚠️ Erro ao interpretar as equipes selecionadas."}]
                }), 400
            equipes_filtradas = {str(item).strip() for item in selecionadas_lista if str(item).strip()}
            equipes_selecionadas = equipes_filtradas or None

        if equipes_permitidas:
            if equipes_selecionadas:
                equipes_selecionadas = {
                    equipe for equipe in equipes_selecionadas if equipe in equipes_permitidas
                } or None
            if not equipes_selecionadas:
                equipes_selecionadas = set(equipes_permitidas)

        task_id = enqueue_csv_processing(
            filepath,
            ignorar_sabados,
            tipo_relatorio,
            equipes_selecionadas,
            debug_mode,
            nome_relatorio=nome_relatorio_normalizado,
            nome_relatorio_original=nome_relatorio_original,
            equipes_permitidas=equipes_permitidas,
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
            "log": [{"type": "error", "message": "⚠️ Erro ao agendar processamento."}]
        }), 500


@api_bp.route('/relatorios/status', methods=['GET'])
def consultar_status_relatorio():
    nome_relatorio = (request.args.get('nome') or '').strip()
    if not nome_relatorio:
        return jsonify({"success": False, "error": "Nome do relatório não informado."}), 400

    status_relatorio = obter_status_relatorio(nome_relatorio)
    if not status_relatorio:
        return jsonify({"success": True, "status": "novo", "relatorio": None})

    return jsonify({
        "success": True,
        "status": status_relatorio.get('status') or "novo",
        "relatorio": status_relatorio,
    })


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


@api_bp.route('/historico/dados', methods=['GET'])
def historico_envios():
    """Retorna o historico de envios com filtros opcionais."""
    equipes_param = [valor.strip() for valor in request.args.getlist('equipes') if valor and valor.strip()]
    tipos_param = [valor.strip() for valor in request.args.getlist('tipos') if valor and valor.strip()]

    single_equipe = (request.args.get('equipe') or '').strip()
    if single_equipe and not equipes_param:
        equipes_param = [single_equipe]

    single_tipo = (request.args.get('tipo') or '').strip()
    if single_tipo and not tipos_param:
        tipos_param = [single_tipo]

    inicio = request.args.get('inicio')
    fim = request.args.get('fim')
    dados = listar_envios(
        equipe=equipes_param or None,
        tipo=tipos_param or None,
        inicio=inicio,
        fim=fim,
    )
    resumo = {
        "total": len(dados),
        "sucessos": sum(1 for item in dados if item.get('status') == 'sucesso'),
        "erros": sum(1 for item in dados if item.get('status') == 'erro'),
    }
    equipes_disponiveis = listar_equipes_disponiveis()
    return jsonify({
        "success": True,
        "dados": dados,
        "resumo": resumo,
        "equipes": equipes_disponiveis,
    })


@api_bp.route('/historico/exportar', methods=['GET'])
def exportar_historico():
    """Gera um arquivo Excel com o historico no formato hierarquico."""
    equipes_param = [valor.strip() for valor in request.args.getlist('equipes') if valor and valor.strip()]
    tipos_param = [valor.strip() for valor in request.args.getlist('tipos') if valor and valor.strip()]

    single_equipe = (request.args.get('equipe') or '').strip()
    if single_equipe and not equipes_param:
        equipes_param = [single_equipe]

    single_tipo = (request.args.get('tipo') or '').strip()
    if single_tipo and not tipos_param:
        tipos_param = [single_tipo]

    inicio = request.args.get('inicio')
    fim = request.args.get('fim')

    registros = listar_envios(
        equipe=equipes_param or None,
        tipo=tipos_param or None,
        inicio=inicio,
        fim=fim,
    )
    arquivo = gerar_planilha_historico(registros)

    nome_arquivo = f"historico-envios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        arquivo,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
