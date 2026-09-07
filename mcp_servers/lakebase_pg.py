# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastmcp>=2.0",
#   "psycopg2-binary>=2.9",
# ]
# ///
"""MCP-сервер к Lakebase (Postgres), только на чтение.

Сосед databricks_uc.py и устроен так же. Причина завести свой та же:
готового сервера с защитой от записи нет. Пакет mcp-server-postgres с
PyPI на эту роль не годится — внутри него одна функция, возвращающая
"Hello from mcp-server-postgres!", исполняемых файлов нет вовсе.

Строка подключения приходит переменной LAKEBASE_DSN, а не аргументом
командной строки: аргументы видны всей машине в ps, и пароль от прода
там оказываться не должен.

Защита тройная, и каждый слой закрывает то, что не закрывают соседние:
роль в БД выдана только на SELECT, сессия открывается read-only на
стороне сервера, и запрос разбирается до отправки. Гранты меняются не
нами и не здесь; своя проверка переживает их изменение и объясняет отказ
внятно, вместо ошибки прав из глубины драйвера.
"""
import os
import re

import psycopg2
from fastmcp import FastMCP

MAX_ROWS = int(os.environ.get("LAKEBASE_MAX_ROWS", "1000"))
NAME = os.environ.get("LAKEBASE_NAME", "lakebase")

# Что разрешено начинать запрос. Всё остальное отклоняется до отправки
ALLOWED_HEADS = ("select", "show", "table", "values", "with", "explain")
# Слова, которых не должно быть нигде в запросе — даже внутри CTE:
# WITH ... INSERT в Postgres синтаксически возможен, и одной проверки
# первого слова мало
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|"
    r"copy|refresh|call|do|set|reset|vacuum|analyze|cluster|reindex|lock|"
    r"listen|notify|prepare|execute|discard|security)\b", re.I)

_COMMENT_LINE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_STRINGS = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")
_HAS_LIMIT = re.compile(r"\blimit\s+\d+\s*$", re.I)

mcp = FastMCP(f"lakebase-{NAME}")


class Refused(Exception):
    """Запрос отклонён защитой, до обращения к базе."""


def _strip(query: str) -> str:
    """Запрос без комментариев и строковых литералов.

    Литералы убираем до поиска запрещённых слов: товар с названием
    «Set of drills» не должен выглядеть как команда SET."""
    q = _COMMENT_BLOCK.sub(" ", query)
    q = _COMMENT_LINE.sub(" ", q)
    return _STRINGS.sub("''", q)


def guard(query: str) -> str:
    """Проверяет запрос и возвращает его готовым к отправке.

    Отказ — исключение с внятным текстом, а не тихое усечение: молча
    выполнить не то, что просили, хуже, чем отказать."""
    bare = _strip(query).strip()
    if not bare:
        raise Refused("Пустой запрос.")

    # Несколько команд через ; — самый простой способ протащить запись
    # следом за безобидным SELECT
    parts = [p for p in bare.split(";") if p.strip()]
    if len(parts) > 1:
        raise Refused(
            f"Отклонено: в запросе {len(parts)} команд через «;». "
            "Разрешена ровно одна — иначе рядом с SELECT можно провезти запись.")
    bare = parts[0].strip()

    head = bare.split(None, 1)[0].lower() if bare.split() else ""
    if head not in ALLOWED_HEADS:
        raise Refused(
            f"Отклонено: запрос начинается с «{head.upper()}». "
            f"Сервер только для чтения, разрешены: "
            f"{', '.join(w.upper() for w in ALLOWED_HEADS)}.")

    found = FORBIDDEN.search(bare)
    if found:
        raise Refused(
            f"Отклонено: в запросе есть «{found.group(0).upper()}». "
            "Даже внутри WITH или подзапроса менять данные нельзя.")

    out = query.strip().rstrip(";").strip()
    if head in ("select", "with", "table") and not _HAS_LIMIT.search(_strip(out).strip()):
        out = f"{out}\nLIMIT {MAX_ROWS}"
    return out


def _connect():
    """Соединение, открытое только на чтение.

    readonly ставится на стороне Postgres: это единственный слой, который
    работает и тогда, когда разбор запроса чего-то не углядел."""
    con = psycopg2.connect(os.environ["LAKEBASE_DSN"], connect_timeout=20)
    con.set_session(readonly=True, autocommit=True)
    return con


def _rows(query: str, params=None, limit: int = MAX_ROWS) -> dict:
    """Результат запроса или текст ошибки в том же виде.

    Исключение драйвера наружу не пускаем: у инструмента MCP оно
    превращается в падение вызова, и вместо «таблицы нет» модель видит
    трассировку на двадцать строк."""
    try:
        with _connect() as con, con.cursor() as cur:
            cur.execute(query, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            data = cur.fetchmany(limit) if cols else []
    except Exception as e:
        first = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        return {"error": first, "query": query}
    return {"columns": cols,
            "rows": [[None if v is None else str(v) for v in r] for r in data],
            "row_count": len(data),
            "truncated": len(data) >= limit}


@mcp.tool()
def list_schemas() -> dict:
    """Схемы базы, кроме служебных."""
    return _rows(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name NOT IN ('pg_catalog', 'information_schema') "
        "AND schema_name NOT LIKE 'pg_%' ORDER BY 1")


@mcp.tool()
def list_tables(schema: str) -> dict:
    """Таблицы и представления схемы, с типом объекта."""
    return _rows(
        "SELECT table_name, table_type FROM information_schema.tables "
        "WHERE table_schema = %s ORDER BY 1", (schema,))


@mcp.tool()
def describe_table(schema: str, table: str) -> dict:
    """Колонки таблицы: имя, тип, допустимость NULL."""
    return _rows(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s "
        "ORDER BY ordinal_position", (schema, table))


@mcp.tool()
def run_query(query: str, limit: int = MAX_ROWS) -> dict:
    """Выполняет запрос на чтение.

    Всё, что не SELECT / SHOW / TABLE / VALUES / WITH / EXPLAIN,
    отклоняется до отправки в базу, с объяснением причины."""
    try:
        safe = guard(query)
    except Refused as e:
        return {"error": str(e), "query": query}
    return _rows(safe, None, min(int(limit or MAX_ROWS), MAX_ROWS))


if __name__ == "__main__":
    mcp.run()
