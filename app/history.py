"""Módulo para armazenamento e consulta do histórico de envios."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

try:
    import mysql.connector
    from mysql.connector.connection import MySQLConnection
    from mysql.connector.cursor import MySQLCursor
except ModuleNotFoundError as exc:  # pragma: no cover - dependência externa
    raise ModuleNotFoundError(
        "Não foi possível importar 'mysql.connector'. "
        "Instale o pacote 'mysql-connector-python' para habilitar o registro "
        "em banco de dados MySQL."
    ) from exc

from app.config.settings import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


def _validate_db_settings() -> None:
    """Garante que as variáveis mínimas de conexão estão definidas."""
    if not DB_NAME:
        raise ValueError("A variável de ambiente DB_NAME deve ser configurada.")
    if not DB_USER:
        raise ValueError("A variável de ambiente DB_USER deve ser configurada.")


@contextmanager
def get_connection() -> Iterator[MySQLConnection]:
    """Retorna uma conexão com o banco de dados MySQL."""
    _validate_db_settings()
    connection = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    try:
        yield connection
    finally:
        connection.close()


def _ensure_column(cursor: MySQLCursor, column_name: str, definition: str) -> None:
    """Cria a coluna informada caso ela ainda não exista."""

    cursor.execute("SHOW COLUMNS FROM envios LIKE %s", (column_name,))
    if cursor.fetchone() is None:
        cursor.execute(f"ALTER TABLE envios ADD COLUMN {column_name} {definition}")


def init_db() -> None:
    """Cria a tabela de histórico e garante as colunas necessárias."""

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                (
                    "CREATE TABLE IF NOT EXISTS envios ("
                    "id INT AUTO_INCREMENT PRIMARY KEY,"
                    "data_envio DATETIME NOT NULL,"
                    "equipe VARCHAR(255) NOT NULL,"
                    "tipo_relatorio VARCHAR(255) NOT NULL,"
                    "status VARCHAR(255) NOT NULL,"
                    "pessoa VARCHAR(255) NULL,"
                    "motivo_envio TEXT NULL"
                    ")"
                )
            )
            _ensure_column(cursor, "pessoa", "VARCHAR(255) NULL")
            _ensure_column(cursor, "motivo_envio", "TEXT NULL")
            conn.commit()
        finally:
            cursor.close()


def registrar_envio(
    equipe: str,
    tipo_relatorio: str,
    status: str,
    pessoa: Optional[str] = None,
    motivo_envio: Optional[str] = None,
) -> None:
    """Registra um envio na base de dados com detalhes adicionais."""

    init_db()
    data_envio = datetime.now()

    pessoa_valor: Optional[str]
    if isinstance(pessoa, str):
        pessoa_limpa = pessoa.strip()
        pessoa_valor = pessoa_limpa or None
    else:
        pessoa_valor = None

    motivo_valor: Optional[str]
    if isinstance(motivo_envio, str):
        motivo_limpo = motivo_envio.strip()
        motivo_valor = motivo_limpo or None
    else:
        motivo_valor = None

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                (
                    "INSERT INTO envios (data_envio, equipe, tipo_relatorio, status, pessoa, motivo_envio) "
                    "VALUES (%s, %s, %s, %s, %s, %s)"
                ),
                (data_envio, equipe, tipo_relatorio, status, pessoa_valor, motivo_valor),
            )
            conn.commit()
        finally:
            cursor.close()


def listar_envios(
    equipe: Optional[str] = None,
    tipo: Optional[str] = None,
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retorna uma lista de envios aplicando filtros quando informados."""
    init_db()
    query = [
        "SELECT data_envio, equipe, tipo_relatorio, status, pessoa, motivo_envio FROM envios WHERE 1=1"
    ]
    params: List[Any] = []
    if equipe:
        query.append("AND equipe = %s")
        params.append(equipe)
    if tipo:
        query.append("AND tipo_relatorio = %s")
        params.append(tipo)
    if inicio:
        query.append("AND DATE(data_envio) >= %s")
        params.append(inicio)
    if fim:
        query.append("AND DATE(data_envio) <= %s")
        params.append(fim)
    query.append("ORDER BY id DESC")
    sql = " ".join(query)
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        finally:
            cursor.close()
    registros: List[Dict[str, Any]] = []
    for row in rows:
        data = row.get("data_envio")
        if isinstance(data, datetime):
            data_envio_formatado = data.strftime(DATETIME_FORMAT)
        elif data:
            data_envio_formatado = str(data)
        else:
            data_envio_formatado = ""
        registros.append(
            {
                "data_envio": data_envio_formatado,
                "equipe": row.get("equipe", ""),
                "tipo_relatorio": row.get("tipo_relatorio", ""),
                "status": row.get("status", ""),
                "pessoa": row.get("pessoa") or "",
                "motivo_envio": row.get("motivo_envio") or "",
            }
        )
    return registros
