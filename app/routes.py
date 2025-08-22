from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
import logging
import uuid
from app.processamento.mapear_gerencia import mapear_equipe
from app.processamento.csv_reader import carregar_dados
from app.tasks import enqueue_csv_processing, get_task_status

api_bp = Blueprint('api', __name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@api_bp.route('/enviar', methods=['POST'])
def enviar():
    try:
        file = request.files.get('csvFile')
        ignorar_sabados = request.form.get('ignorarSabados', 'true') == 'true'
        tipo_relatorio = request.form.get('tipoRelatorio', 'Auditoria').strip()
        if tipo_relatorio not in {"Auditoria", "Ocorrências"}:
            return jsonify({
                "success": False,
                "log": [{"type": "error", "message": f"❌ Tipo de relatório inválido: {tipo_relatorio}. Selecione 'Auditoria' ou 'Ocorrências'."}]
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