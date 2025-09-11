"""Módulo para armazenamento e consulta do histórico de envios."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# Caminho do banco de dados SQLite
DB_PATH = Path(__file__).resolve().parent.parent / "historico.db"


def init_db() -> None:
    """Cria a tabela de histórico caso não exista."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            (
                "CREATE TABLE IF NOT EXISTS envios ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "data_envio TEXT NOT NULL,"
                "equipe TEXT NOT NULL,"
                "tipo_relatorio TEXT NOT NULL,"
                "status TEXT NOT NULL"
                ")"
            )
        )
        conn.commit()


def registrar_envio(equipe: str, tipo_relatorio: str, status: str) -> None:
    """Registra um envio na base de dados."""
    init_db()
    data_envio = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO envios (data_envio, equipe, tipo_relatorio, status) VALUES (?, ?, ?, ?)",
            (data_envio, equipe, tipo_relatorio, status),
        )
        conn.commit()


def listar_envios(
    equipe: Optional[str] = None,
    tipo: Optional[str] = None,
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retorna uma lista de envios aplicando filtros quando informados."""
    init_db()
    query = [
        "SELECT data_envio, equipe, tipo_relatorio, status FROM envios WHERE 1=1"
    ]
    params: List[str] = []
    if equipe:
        query.append("AND equipe = ?")
        params.append(equipe)
    if tipo:
        query.append("AND tipo_relatorio = ?")
        params.append(tipo)
    if inicio:
        query.append("AND date(data_envio) >= date(?)")
        params.append(inicio)
    if fim:
        query.append("AND date(data_envio) <= date(?)")
        params.append(fim)
    query.append("ORDER BY data_envio DESC")
    sql = " ".join(query)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
