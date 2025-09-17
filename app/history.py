"""Módulo para armazenamento e consulta do histórico de envios.

Responsável por:
- Garantir a existência do banco e da tabela de histórico
- Registrar envios (sucesso/erro) com metadados
- Listar envios com filtros simples

Observações:
- Usa MySQL via ``mysql-connector-python``
- Força ``utf8mb4`` para suportar acentuação e emojis
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import mysql.connector
from mysql.connector.connection import MySQLConnection
from mysql.connector.cursor import MySQLCursor
from mysql.connector import errorcode, Error as MySQLError
import logging

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


def _ensure_database() -> None:
    """Cria o banco de dados se ele não existir.

    Observação: Requer permissão de ``CREATE DATABASE`` para o usuário.
    Caso não tenha permissão, crie o banco manualmente:
        CREATE DATABASE `%(db)s` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """
    _validate_db_settings()
    try:
        srv = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True,
        )
        try:
            cur = srv.cursor()
            cur.execute(
                (
                    f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        finally:
            cur.close()
            srv.close()
    except MySQLError as exc:  # noqa: BLE001
        logging.error("Falha ao garantir database '%s': %s", DB_NAME, exc)
        # Não interrompe forçosamente: a conexão abaixo pode funcionar se o DB já existir


@contextmanager
def get_connection() -> Iterator[MySQLConnection]:
    """Retorna uma conexão com o banco MySQL, garantindo UTF-8."""
    _validate_db_settings()
    _ensure_database()
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            charset="utf8mb4",
            use_unicode=True,
            autocommit=False,
            raise_on_warnings=False,
        )
    except MySQLError as exc:  # noqa: BLE001
        logging.error(
            "Erro ao conectar no MySQL %s:%s/%s: %s",
            DB_HOST,
            DB_PORT,
            DB_NAME,
            exc,
        )
        raise
    try:
        yield connection
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass


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
                        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
                    )
                )
            except MySQLError as exc:  # noqa: BLE001
                if exc.errno not in {errorcode.ER_TABLE_EXISTS_ERROR, errorcode.ER_DB_CREATE_EXISTS}:
                    logging.error("Erro ao criar tabela de histórico: %s", exc)
                    raise
            # Redundante, mas mantém compatibilidade caso a tabela exista com schema antigo
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

    logging.info(
        "Registrando envio no histórico: equipe=%s, tipo=%s, status=%s, pessoa=%s",
        str(equipe).strip(), str(tipo_relatorio).strip(), str(status).strip(), pessoa_valor or "",
    )

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
        except MySQLError as exc:  # noqa: BLE001
            logging.error("Erro ao inserir histórico: %s", exc)
            raise
        finally:
            cursor.close()


def listar_envios(
    equipe: Optional[object] = None,
    tipo: Optional[object] = None,
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retorna uma lista de envios aplicando filtros quando informados."""
    init_db()
    query = [
        "SELECT data_envio, equipe, tipo_relatorio, status, pessoa, motivo_envio FROM envios WHERE 1=1"
    ]
    params: List[Any] = []

    def _prepare_lista(valor: object) -> List[str]:
        if valor is None:
            return []
        if isinstance(valor, (list, tuple, set)):
            return [str(item).strip() for item in valor if str(item).strip()]
        texto = str(valor).strip()
        return [texto] if texto else []

    equipes = _prepare_lista(equipe)
    tipos = _prepare_lista(tipo)

    if equipes:
        if len(equipes) == 1:
            query.append("AND equipe = %s")
            params.append(equipes[0])
        else:
            placeholders = ', '.join(['%s'] * len(equipes))
            query.append(f"AND equipe IN ({placeholders})")
            params.extend(equipes)

    if tipos:
        if len(tipos) == 1:
            query.append("AND tipo_relatorio = %s")
            params.append(tipos[0])
        else:
            placeholders = ', '.join(['%s'] * len(tipos))
            query.append(f"AND tipo_relatorio IN ({placeholders})")
            params.extend(tipos)

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
        except MySQLError as exc:  # noqa: BLE001
            logging.error("Erro ao consultar historico: %s", exc)
            raise
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



def listar_equipes_disponiveis() -> List[str]:
    """Retorna todas as equipes registradas no histórico."""

    init_db()
    equipes: List[str] = []
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT equipe FROM envios ORDER BY equipe ASC")
            for (equipe,) in cursor.fetchall():
                if not equipe:
                    continue
                equipes.append(str(equipe))
        except MySQLError as exc:  # noqa: BLE001
            logging.error("Erro ao listar equipes do histórico: %s", exc)
            raise
        finally:
            cursor.close()
    return equipes
