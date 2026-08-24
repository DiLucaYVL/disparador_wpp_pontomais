from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import json
import logging
import uuid
import random
import time
import threading
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

CONNECTING_TIMEOUT_SECONDS = 60
_connecting_since: float | None = None
_connecting_lock = threading.Lock()

def _evo_headers():
    return {"Content-Type": "application/json", "apikey": EVOLUTION_TOKEN}

def _desconectar_instancia() -> bool:
    """Envia requisição de logout para a Evolution API para fechar a sessão."""
    try:
        url = urljoin(EVOLUTION_URL, f"/instance/logout/{EVOLUTION_INSTANCE}")
        resp = requests.delete(url, headers=_evo_headers(), timeout=15)
        return resp.status_code in (200, 201)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Erro ao tentar desconectar instância %s: %s", EVOLUTION_INSTANCE, exc)
        return False

def _extrair_estado(data, instance_name: str) -> str | None:
    """Extrai o estado de conexão da instância a partir da resposta da Evolution API."""
    if not data:
        return None

    target = data
    if isinstance(data, list):
        target = next(
            (
                item for item in data
                if isinstance(item, dict) and (
                    item.get("instance", {}).get("instanceName") == instance_name
                    or item.get("instanceName") == instance_name
                    or item.get("name") == instance_name
                )
            ),
            data[0] if len(data) == 1 and isinstance(data[0], dict) else None,
        )

    if not isinstance(target, dict):
        return None

    inst = target.get("instance") if isinstance(target.get("instance"), dict) else target

    estado = (
        inst.get("state")
        or inst.get("status")
        or (inst.get("connectionStatus", {}).get("state") if isinstance(inst.get("connectionStatus"), dict) else None)
        or (target.get("connectionStatus", {}).get("state") if isinstance(target.get("connectionStatus"), dict) else None)
        or target.get("state")
        or target.get("status")
    )

    if isinstance(estado, str):
        return estado.strip().lower()

    return None

def verificar_sessao() -> tuple[bool, str]:
    """Garante que a sessão do WhatsApp esteja ativa.

    Tenta obter o status da instância consultando a Evolution API.
    Se a instância permanecer em 'connecting' por mais de 60 segundos,
    força o encerramento da sessão (logout) para que retorne a 'close'.

    Returns:
        Uma tupla contendo (True, "open") ou (False, estado).
    """
    global _connecting_since

    urls_tentativas = [
        urljoin(EVOLUTION_URL, f"/instance/connectionState/{EVOLUTION_INSTANCE}"),
        urljoin(
            EVOLUTION_URL,
            f"/instance/fetchInstances?instanceName={EVOLUTION_INSTANCE}",
        ),
    ]

    ultimo_estado = "close"

    for url in urls_tentativas:
        try:
            resp = requests.get(url, headers=_evo_headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()

            estado = _extrair_estado(data, EVOLUTION_INSTANCE)
            if estado:
                ultimo_estado = estado
                if estado == "open":
                    with _connecting_lock:
                        _connecting_since = None
                    return True, "open"
                break

        except requests.RequestException as exc:
            logging.warning("Falha ao verificar sessão na URL %s: %s", url, exc)
        except Exception:
            logging.warning("Erro inesperado ao processar resposta da URL %s.", url)

    with _connecting_lock:
        if ultimo_estado == "connecting":
            agora = time.time()
            if _connecting_since is None:
                _connecting_since = agora
            elif agora - _connecting_since >= CONNECTING_TIMEOUT_SECONDS:
                logging.warning(
                    "Instância %s permaneceu em 'connecting' por mais de %ds. Forçando logout para 'close'.",
                    EVOLUTION_INSTANCE,
                    CONNECTING_TIMEOUT_SECONDS,
                )
                _desconectar_instancia()
                _connecting_since = None
                ultimo_estado = "close"
        else:
            _connecting_since = None

    return False, ultimo_estado

def enviar_whatsapp(numero, mensagem, equipe=None):
    sessao_ativa, _ = verificar_sessao()
    if not sessao_ativa:
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
        return jsonify({
            "success": True,
            "status": "pending",
            "message": "Status da tarefa ainda não está disponível. Tente novamente em instantes."
        }), 202
    status_atual = (task.get("status") or "").strip() or "pending"
    if status_atual == "done":
        result = task.get("result") or {}
        return jsonify({
            "success": True,
            "status": "done",
            "log": result.get("logs", []),
            "stats": result.get("stats", {}),
            "debug": result.get("debug"),
            "nome_arquivo_log": result.get("nome_arquivo_log"),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
        })
    if status_atual == "error":
        return jsonify({
            "success": False,
            "status": "error",
            "error": task.get("error", "Erro desconhecido."),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
        })
    return jsonify({
        "success": True,
        "status": status_atual,
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
    })
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
        conectado, estado = verificar_sessao()
        return jsonify({
            "success": True,
            "connected": conectado,
            "status": estado,
            "state": estado,
        })
    except Exception as exc:  # noqa: BLE001
        logging.exception("Erro ao obter status do WhatsApp")
        return jsonify({
            "success": False,
            "connected": False,
            "status": "error",
            "state": "error",
            "error": str(exc),
        }), 500

@api_bp.route('/whatsapp/qr', methods=['GET'])
def whatsapp_qr():
    """Tenta conectar e retorna o QR code, se aplicável."""
    try:
        url = urljoin(EVOLUTION_URL, f"/instance/connect/{EVOLUTION_INSTANCE}")
        resp = requests.get(url, headers=_evo_headers(), timeout=45)
        resp.raise_for_status()

        data = resp.json()
        qr_code = None
        if isinstance(data, dict):
            qr_code = data.get("base64")
            if not qr_code and isinstance(data.get("qrcode"), dict):
                qr_code = data.get("qrcode", {}).get("base64")
            elif not qr_code and isinstance(data.get("qrcode"), str):
                qr_code = data.get("qrcode")
            if not qr_code:
                qr_code = data.get("code")

        return jsonify(
            {
                "success": True,
                "instance": EVOLUTION_INSTANCE,
                "qr_code": qr_code,
            }
        )
    except requests.RequestException as exc:
        logging.error("Erro de comunicação ao obter QR Code: %s", exc)
        return jsonify({"success": False, "error": "Falha de comunicação com a API", "details": str(exc)}), 502
    except Exception as exc:  # noqa: BLE001
        logging.exception("Erro inesperado ao obter QR Code do WhatsApp")
        return jsonify({"success": False, "error": "Erro interno do servidor", "details": str(exc)}), 500

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
