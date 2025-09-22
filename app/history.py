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
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, TypedDict, Union

import mysql.connector
from mysql.connector.connection import MySQLConnection
from mysql.connector.cursor import MySQLCursor
from mysql.connector import errorcode, Error as MySQLError
import logging
from werkzeug.utils import secure_filename

from app.config.settings import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"

STATUS_SUCESSO_TOTAL = "sucesso_total"
STATUS_ENVIO_PARCIAL = "parcial"


def normalizar_nome_relatorio(nome: Optional[str]) -> str:
    """Normaliza o nome do relat?rio para uso como chave ?nica."""

    if not isinstance(nome, str):
        return ""
    nome_limpo = secure_filename(nome).strip()
    return nome_limpo.lower()



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
            allow_local_infile=True,
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
            _ensure_column(cursor, "nome_relatorio", "VARCHAR(255) NULL")
            conn.commit()
        finally:
            cursor.close()



def _init_relatorio_tables() -> None:
    """Garante as tabelas auxiliares de controle de relatórios."""

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                (
                    "CREATE TABLE IF NOT EXISTS relatorios ("
                    "id INT AUTO_INCREMENT PRIMARY KEY,"
                    "nome_relatorio VARCHAR(255) NOT NULL UNIQUE,"
                    "nome_original VARCHAR(255) NULL,"
                    "tipo_relatorio VARCHAR(255) NOT NULL,"
                    "status VARCHAR(32) NOT NULL,"
                    "total_mensagens INT NOT NULL DEFAULT 0,"
                    "mensagens_sucesso INT NOT NULL DEFAULT 0,"
                    "mensagens_erro INT NOT NULL DEFAULT 0,"
                    "atualizado_em DATETIME NOT NULL"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
                )
            )
            cursor.execute(
                (
                    "CREATE TABLE IF NOT EXISTS relatorio_pendencias ("
                    "id INT AUTO_INCREMENT PRIMARY KEY,"
                    "relatorio_id INT NOT NULL,"
                    "equipe VARCHAR(255) NOT NULL,"
                    "registrado_em DATETIME NOT NULL,"
                    "UNIQUE KEY relatorio_equipe (relatorio_id, equipe),"
                    "CONSTRAINT fk_relatorio_pendencias_relatorio "
                    "FOREIGN KEY (relatorio_id) REFERENCES relatorios (id) "
                    "ON DELETE CASCADE"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
                )
            )
            conn.commit()
        except MySQLError as exc:  # noqa: BLE001
            conn.rollback()
            logging.error("Erro ao garantir tabelas de relatorio: %s", exc)
            raise
        finally:
            cursor.close()


def registrar_resultado_relatorio(
nome_relatorio: Optional[str],
    nome_original: Optional[str],
tipo_relatorio: str,
    total: int,
    sucesso: int,
    erro: int,
    equipes_com_erro: Optional[Iterable[str]] = None,
) -> None:
    """Armazena o status consolidado de um relatório e suas pendências."""

    nome_chave = normalizar_nome_relatorio(nome_relatorio)
    if not nome_chave:
        logging.warning("Nome de relatório inválido para registro de resultado: %s", nome_relatorio)
        return

    nome_original_valor = (nome_original or nome_relatorio or nome_chave).strip()
    total_int = int(total or 0)
    sucesso_int = int(sucesso or 0)
    erro_int = int(erro or 0)
    status_final = STATUS_SUCESSO_TOTAL if erro_int <= 0 and sucesso_int >= total_int else STATUS_ENVIO_PARCIAL
    equipes_falhas = []
    if equipes_com_erro:
        equipes_falhas = sorted({str(equipe).strip() for equipe in equipes_com_erro if str(equipe).strip()})

    _init_relatorio_tables()
    agora = datetime.now()

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id FROM relatorios WHERE nome_relatorio = %s",
                (nome_chave,),
            )
            row = cursor.fetchone()
            if row:
                relatorio_id = row[0]
                cursor.execute(
                    (
                        "UPDATE relatorios SET nome_original = %s, tipo_relatorio = %s, status = %s, "
                        "total_mensagens = %s, mensagens_sucesso = %s, mensagens_erro = %s, atualizado_em = %s "
                        "WHERE id = %s"
                    ),
                    (
                        nome_original_valor,
                        tipo_relatorio,
                        status_final,
                        total_int,
                        sucesso_int,
                        erro_int,
                        agora,
                        relatorio_id,
                    ),
                )
            else:
                cursor.execute(
                    (
                        "INSERT INTO relatorios "
                        "(nome_relatorio, nome_original, tipo_relatorio, status, total_mensagens, mensagens_sucesso, mensagens_erro, atualizado_em) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                    ),
                    (
                        nome_chave,
                        nome_original_valor,
                        tipo_relatorio,
                        status_final,
                        total_int,
                        sucesso_int,
                        erro_int,
                        agora,
                    ),
                )
                relatorio_id = cursor.lastrowid

            cursor.execute(
                "DELETE FROM relatorio_pendencias WHERE relatorio_id = %s",
                (relatorio_id,),
            )
            if status_final == STATUS_ENVIO_PARCIAL and equipes_falhas:
                for equipe in equipes_falhas:
                    cursor.execute(
                        (
                            "INSERT INTO relatorio_pendencias (relatorio_id, equipe, registrado_em) "
                            "VALUES (%s, %s, %s) "
                            "ON DUPLICATE KEY UPDATE registrado_em = VALUES(registrado_em)"
                        ),
                        (relatorio_id, equipe, agora),
                    )
            conn.commit()
        except MySQLError as exc:  # noqa: BLE001
            conn.rollback()
            logging.error("Erro ao registrar resumo do relatorio %s: %s", nome_chave, exc)
            raise
        finally:
            cursor.close()


def obter_status_relatorio(nome_relatorio: Optional[str]) -> Optional[Dict[str, Any]]:
    """Busca o resumo consolidado de um relatório pelo nome."""

    nome_chave = normalizar_nome_relatorio(nome_relatorio)
    if not nome_chave:
        return None

    _init_relatorio_tables()

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                (
                    "SELECT id, nome_relatorio, nome_original, tipo_relatorio, status, "
                    "total_mensagens, mensagens_sucesso, mensagens_erro, atualizado_em "
                    "FROM relatorios WHERE nome_relatorio = %s"
                ),
                (nome_chave,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            relatorio_id = row["id"]
            cursor_pend = conn.cursor()
            try:
                cursor_pend.execute(
                    "SELECT equipe FROM relatorio_pendencias WHERE relatorio_id = %s ORDER BY equipe ASC",
                    (relatorio_id,),
                )
                pendencias = [str(item[0]) for item in cursor_pend.fetchall() if item and item[0]]
            finally:
                cursor_pend.close()

            atualizado = row.get("atualizado_em")
            if isinstance(atualizado, datetime):
                atualizado_formatado = atualizado.strftime(DATETIME_FORMAT)
            elif atualizado:
                atualizado_formatado = str(atualizado)
            else:
                atualizado_formatado = ""

            return {
                "nome_relatorio": row.get("nome_relatorio"),
                "nome_original": row.get("nome_original") or row.get("nome_relatorio"),
                "tipo_relatorio": row.get("tipo_relatorio") or "",
                "status": row.get("status") or "",
                "total": int(row.get("total_mensagens") or 0),
                "sucesso": int(row.get("mensagens_sucesso") or 0),
                "erro": int(row.get("mensagens_erro") or 0),
                "atualizado_em": atualizado_formatado,
                "pendencias": pendencias,
            }
        except MySQLError as exc:  # noqa: BLE001
            logging.error("Erro ao obter status do relatorio %s: %s", nome_chave, exc)
            raise
        finally:
            cursor.close()



class EnvioRegistro(TypedDict, total=False):
    """Estrutura padrao para registrar um envio no historico."""

    equipe: str
    tipo_relatorio: str
    status: str
    pessoa: Optional[str]
    motivo_envio: Optional[str]
    nome_relatorio: Optional[str]
    data_envio: Optional[datetime]


PreparedEnvio = Tuple[
    datetime,
    str,
    str,
    str,
    Optional[str],
    Optional[str],
    Optional[str],
]

def _texto_opcional(valor: object) -> Optional[str]:
    """Normaliza textos opcionais removendo espacos e vazios."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        valor = str(valor)
    texto = valor.strip()
    return texto or None

def _texto_obrigatorio(valor: object, campo: str) -> str:
    """Garante que um campo obrigatorio foi informado."""
    texto = _texto_opcional(valor)
    if texto is None:
        raise ValueError(f"O campo '{campo}' e obrigatorio para registrar o envio.")
    return texto

def _preparar_envios(envios: Sequence[EnvioRegistro]) -> List[PreparedEnvio]:
    """Transforma a estrutura de envios em tuplas prontas para o MySQL."""
    registros: List[PreparedEnvio] = []
    for envio in envios:
        equipe = _texto_obrigatorio(envio.get("equipe"), "equipe")
        tipo_relatorio = _texto_obrigatorio(envio.get("tipo_relatorio"), "tipo_relatorio")
        status = _texto_obrigatorio(envio.get("status"), "status")
        pessoa = _texto_opcional(envio.get("pessoa"))
        motivo = _texto_opcional(envio.get("motivo_envio"))
        nome_relatorio_valor: Optional[str] = None
        nome_bruto = envio.get("nome_relatorio")
        if nome_bruto is not None:
            nome_normalizado = normalizar_nome_relatorio(nome_bruto)
            nome_relatorio_valor = nome_normalizado or None
        data_bruta = envio.get("data_envio")
        data_valor = datetime.now()
        if isinstance(data_bruta, datetime):
            data_valor = data_bruta
        elif isinstance(data_bruta, str):
            candidato = data_bruta.strip()
            if candidato:
                try:
                    data_valor = datetime.fromisoformat(candidato)
                except ValueError:
                    logging.debug("Data '%s' invalida; usando timestamp atual.", candidato)
        registros.append((
            data_valor,
            equipe,
            tipo_relatorio,
            status,
            pessoa,
            motivo,
            nome_relatorio_valor,
        ))
    return registros

def _executar_batches(
    cursor: MySQLCursor,
    registros: Sequence[PreparedEnvio],
    batch_size: int,
    sql: str,

) -> None:
    """Executa insercoes em lote utilizando executemany."""
    for inicio in range(0, len(registros), batch_size):
        lote = registros[inicio : inicio + batch_size]
        cursor.executemany(sql, lote)

def _executar_load_data(cursor: MySQLCursor, arquivo: Path, local: bool) -> None:
    """Importa registros via LOAD DATA (LOCAL) INFILE."""
    if not arquivo.is_file():
        raise FileNotFoundError(
            f"Arquivo '{arquivo}' nao encontrado para LOAD DATA."
        )
    caminho_literal = str(arquivo).replace("\\", "\\\\").replace("'", "\'")
    prefixo_local = "LOCAL " if local else ""
    sql = "".join(
        [
            f"LOAD DATA {prefixo_local}INFILE '{caminho_literal}' ",
            "INTO TABLE envios ",
            "FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '",
            chr(34),
            "' ",
            "LINES TERMINATED BY '\n' ",
            "(data_envio, equipe, tipo_relatorio, status, pessoa, motivo_envio, nome_relatorio)",
        ]
    )
    cursor.execute(sql)

def _inserir_individualmente(
    conn: MySQLConnection,
    registros: Sequence[PreparedEnvio],
    sql: str,

) -> None:
    """Fallback para inserir registros um a um quando o lote falha."""
    logging.warning(
        "Executando fallback individual para %d registros no historico.",
        len(registros),
    )
    cursor = conn.cursor()
    try:
        for item in registros:
            cursor.execute(sql, item)
        conn.commit()
    except MySQLError as exc:  # noqa: BLE001
        conn.rollback()
        logging.error("Fallback individual falhou: %s", exc)
        raise
    finally:
        cursor.close()

def registrar_envio(
    envios: Union[str, EnvioRegistro, Iterable[EnvioRegistro]],
    tipo_relatorio: Optional[str] = None,
    status: Optional[str] = None,
    pessoa: Optional[str] = None,
    motivo_envio: Optional[str] = None,
    nome_relatorio: Optional[str] = None,
    *,
    batch_size: int = 500,
    usar_load_data: bool = False,
    arquivo_csv: Optional[Union[str, Path]] = None,
    load_data_local: bool = True,
    fallback_para_individual: bool = True,

) -> None:
    """Registra envios no historico utilizando insercoes em lote.

    A funcao aceita tanto a assinatura antiga (parametros individuais) quanto
    uma lista de envios. Quando recebe multiplos registros eles sao agrupados
    em blocos de ate ``batch_size`` itens e enviados via ``cursor.executemany``
    em uma unica transacao. Opcionalmente e possivel informar ``arquivo_csv``
    para executar ``LOAD DATA`` (ou ``LOAD DATA LOCAL``) quando ja houver um
    arquivo com os dados.

    Exemplo:
        >>> envios = [
        ...     {"equipe": "Equipe Financeiro", "tipo_relatorio": "fechamento", "status": "sucesso"}
        ...     for _ in range(500)
        ... ]
        >>> registrar_envio(envios, batch_size=200)
    """
    init_db()
    if batch_size <= 0:
        raise ValueError("batch_size deve ser um inteiro positivo.")
    if isinstance(envios, dict):
        if any(
            valor is not None
            for valor in (tipo_relatorio, status, pessoa, motivo_envio, nome_relatorio)
        ):
            raise ValueError(
                "Nao informe parametros adicionais ao passar um unico envio como dicionario."
            )
        envios_preparados = [envios]
    elif isinstance(envios, str):
        if not tipo_relatorio:
            raise ValueError(
                "tipo_relatorio e obrigatorio quando apenas uma equipe e informada."
            )
        if not status:
            raise ValueError(
                "status e obrigatorio quando apenas uma equipe e informada."
            )
        envio_unico: EnvioRegistro = {
            "equipe": envios,
            "tipo_relatorio": tipo_relatorio,
            "status": status,
        }
        if pessoa is not None:
            envio_unico["pessoa"] = pessoa
        if motivo_envio is not None:
            envio_unico["motivo_envio"] = motivo_envio
        if nome_relatorio is not None:
            envio_unico["nome_relatorio"] = nome_relatorio
        envios_preparados = [envio_unico]
    else:
        envios_preparados = list(envios)
        if any(
            valor is not None
            for valor in (tipo_relatorio, status, pessoa, motivo_envio, nome_relatorio)
        ):
            raise ValueError(
                "Parametros individuais nao podem ser combinados com a lista de envios."
            )
    registros = _preparar_envios(envios_preparados)
    if not registros:
        logging.info("Nenhum envio informado para registro.")
        return
    total_registros = len(registros)
    caminho_csv: Optional[Path] = None
    if arquivo_csv is not None:
        caminho_csv = Path(arquivo_csv).expanduser()
    usar_load = usar_load_data or caminho_csv is not None
    logging.info(
        "Registrando %d envios no historico (batch_size=%d, load_data=%s).",
        total_registros,
        batch_size,
        usar_load,
    )
    sql_insert = (
        "INSERT INTO envios "
        "(data_envio, equipe, tipo_relatorio, status, pessoa, motivo_envio, nome_relatorio) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            if usar_load:
                if caminho_csv is None:
                    raise ValueError(
                        "Informe 'arquivo_csv' para utilizar LOAD DATA no registrar_envio."
                    )
                _executar_load_data(cursor, caminho_csv, load_data_local)
            else:
                _executar_batches(cursor, registros, batch_size, sql_insert)
        except MySQLError as exc:  # noqa: BLE001
            conn.rollback()
            logging.error(
                "Erro ao inserir lote de envios (total=%d): %s",
                total_registros,
                exc,
            )
            if not usar_load and fallback_para_individual:
                _inserir_individualmente(conn, registros, sql_insert)
                return
            raise
        else:
            conn.commit()
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
        "SELECT data_envio, equipe, tipo_relatorio, status, pessoa, motivo_envio, nome_relatorio FROM envios WHERE 1=1"
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
                "nome_relatorio": row.get("nome_relatorio") or "",
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
