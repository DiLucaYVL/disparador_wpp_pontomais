import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.controller import processar_csv

# Executor global por processo
_executor = ThreadPoolExecutor(max_workers=4)
_tasks = {}


def enqueue_csv_processing(filepath: str, ignorar_sabados: bool, tipo_relatorio: str,
                           equipes_selecionadas: Optional[set] = None,
                           debug_mode: bool = False) -> str:
    """Agenda o processamento do CSV em background."""
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {"status": "queued", "result": None, "error": None}

    def _run():
        _tasks[task_id]["status"] = "running"
        try:
            logs, stats, nome_arquivo_log, resumo_matricial = processar_csv(
                filepath, ignorar_sabados, tipo_relatorio, equipes_selecionadas
            )

            debug_data = None
            if debug_mode:
                if tipo_relatorio == "Ocorrências":
                    from app.processamento.csv_reader_ocorrencias import carregar_dados_ocorrencias
                    debug_data = carregar_dados_ocorrencias(filepath).to_json(
                        orient="records", force_ascii=False
                    )
                else:
                    from app.processamento.csv_reader import carregar_dados
                    debug_data = carregar_dados(
                        filepath, ignorar_sabados, tipo_relatorio
                    ).to_json(orient="records", force_ascii=False)

            _tasks[task_id]["result"] = {
                "logs": logs,
                "stats": stats,
                "nome_arquivo_log": nome_arquivo_log,
                "resumo": resumo_matricial,
                "debug": debug_data,
            }
            _tasks[task_id]["status"] = "done"
        except Exception as e:  # noqa: BLE001 - registrar erro genericamente
            _tasks[task_id]["error"] = str(e)
            _tasks[task_id]["status"] = "error"
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    _executor.submit(_run)
    return task_id


def get_task_status(task_id: str):
    """Obtém o dicionário de status/resultado da tarefa."""
    return _tasks.get(task_id)
