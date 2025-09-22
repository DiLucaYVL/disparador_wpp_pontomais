import json
import logging
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.controller import processar_csv

# Executor global por processo
_executor = ThreadPoolExecutor(max_workers=4)
_tasks: Dict[str, Dict[str, Any]] = {}

TASK_STATUS_DIR = Path('task_status')
TASK_STATUS_DIR.mkdir(parents=True, exist_ok=True)


def _task_file(task_id: str) -> Path:
    return TASK_STATUS_DIR / f"{task_id}.json"


def _sanitize_for_json(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: _sanitize_for_json(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_sanitize_for_json(item) for item in data]
    if isinstance(data, set):
        return [_sanitize_for_json(item) for item in data]
    if isinstance(data, tuple):
        return [_sanitize_for_json(item) for item in data]
    if isinstance(data, Path):
        return str(data)
    return data


def _persist_task_state(
    task_id: str,
    *,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    created_at = _tasks.get(task_id, {}).get('created_at')
    now_iso = datetime.utcnow().isoformat() + 'Z'
    payload = {
        'status': status,
        'result': _sanitize_for_json(result) if result is not None else None,
        'error': error,
        'created_at': created_at or now_iso,
        'updated_at': now_iso,
    }
    _tasks[task_id] = payload

    temp_path: Optional[Path] = None
    try:
        TASK_STATUS_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            'w', encoding='utf-8', delete=False, dir=TASK_STATUS_DIR, suffix='.json'
        ) as tmp_file:
            json.dump(payload, tmp_file, ensure_ascii=False)
            temp_path = Path(tmp_file.name)
        temp_path.replace(_task_file(task_id))
    except Exception as exc:  # noqa: BLE001
        logging.exception('Erro ao persistir status da tarefa %s: %s', task_id, exc)
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _load_task_from_disk(task_id: str) -> Optional[Dict[str, Any]]:
    filepath = _task_file(task_id)
    if not filepath.exists():
        return None
    try:
        with filepath.open('r', encoding='utf-8') as handler:
            data = json.load(handler)
        if isinstance(data, dict):
            _tasks[task_id] = data
            return data
    except Exception as exc:  # noqa: BLE001
        logging.exception('Erro ao carregar status da tarefa %s: %s', task_id, exc)
    return None


def enqueue_csv_processing(
    filepath: str,
    ignorar_sabados: bool,
    tipo_relatorio: str,
    equipes_selecionadas: Optional[set] = None,
    debug_mode: bool = False,
    nome_relatorio: Optional[str] = None,
    nome_relatorio_original: Optional[str] = None,
    equipes_permitidas: Optional[set] = None,
) -> str:
    """Agenda o processamento do CSV em background."""
    task_id = uuid.uuid4().hex
    _persist_task_state(task_id, status='queued', result=None, error=None)

    def _run() -> None:
        _persist_task_state(task_id, status='running', result=None, error=None)
        try:
            logs, stats, nome_arquivo_log = processar_csv(
                filepath,
                ignorar_sabados,
                tipo_relatorio,
                equipes_selecionadas,
                nome_relatorio=nome_relatorio,
                nome_relatorio_original=nome_relatorio_original,
                equipes_permitidas=equipes_permitidas,
            )

            debug_data = None
            if debug_mode:
                if tipo_relatorio == 'Ocorrências':
                    from app.processamento.csv_reader_ocorrencias import carregar_dados_ocorrencias

                    debug_data = carregar_dados_ocorrencias(filepath).to_json(
                        orient='records', force_ascii=False
                    )
                else:
                    from app.processamento.csv_reader import carregar_dados

                    debug_data = carregar_dados(
                        filepath, ignorar_sabados, tipo_relatorio
                    ).to_json(orient='records', force_ascii=False)

            result_payload = {
                'logs': logs,
                'stats': stats,
                'nome_arquivo_log': nome_arquivo_log,
                'debug': debug_data,
            }
            _persist_task_state(task_id, status='done', result=result_payload, error=None)
        except Exception as exc:  # noqa: BLE001 - registrar erro genericamente
            logging.exception('Erro ao processar tarefa %s', task_id)
            _persist_task_state(task_id, status='error', result=None, error=str(exc))
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    _executor.submit(_run)
    return task_id


def get_task_status(task_id: str):
    """Obtém o dicionário de status/resultado da tarefa."""
    task = _tasks.get(task_id)
    if task is not None:
        return task
    return _load_task_from_disk(task_id)
