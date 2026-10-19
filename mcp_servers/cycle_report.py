# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastmcp>=2.0",
#   "psycopg2-binary>=2.9",
# ]
# ///
"""MCP-сервер «сводка цикла»: ОДИН инструмент — записать строку в listing_data.agent_cycle_reports.

Зачем отдельный сервер, а не инструмент в lakebase_pg.py. Тот сервер — только на чтение, и это
держат три слоя: роль, сессия read-only, разбор запроса. Добавить туда запись — значит снять второй
слой для всего сервера. Здесь наоборот: запись есть, но ровно одна, с фиксированным текстом запроса.
SQL агент не передаёт вовсе — только пять строк сводки.

Почему агенту не нужна строка подключения. Её держит процесс сервера: она приходит переменной
LAKEBASE_DSN из записи `ls-cycle-report` в .mcp.json, которую заводит владелец (роль
claude_code_report, пароль — секрет). Агент вызывает инструмент и значения не видит — правило
«значения секретов — никогда сам» не нарушается (AGENTS.md, «Автономия»).

Чего роль не может, и это проверяет база, а не этот файл (migrations/2026-10-19_agent_cycle_reports.sql):
читать таблицу, писать sent_at / send_error / attempts, трогать другие таблицы. Поэтому здесь нет
RETURNING: он требует права на чтение.

Отправляет сводку в бот задача Кабинета «Kabinet - Agent Cycle Report» (docs/autonomy.md).
"""
import os
import re
from urllib.parse import unquote

import psycopg2
from fastmcp import FastMCP

PREFIX = "Listing Suite · "
TITLE_MAX = 200          # шапка сообщения в боте
FIELD_MAX = 4000         # одно поле; Telegram режет сообщение на 4096 знаках
INSERT_SQL = ("INSERT INTO listing_data.agent_cycle_reports (title, done, merged, waiting, problems) "
              "VALUES (%s, %s, %s, %s, %s)")

mcp = FastMCP("ls-cycle-report")


def clean(text, limit: int):
    """Пустое — None (поле не попадает в сообщение), длинное — обрезано с пометкой."""
    text = (text or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def row(title: str, done: str = "", merged: str = "", waiting: str = "", problems: str = "") -> tuple:
    head = (title or "").strip()
    if not head:
        raise ValueError("пустая шапка сводки")
    if not head.startswith(PREFIX):
        head = PREFIX + head
    return (clean(head, TITLE_MAX), clean(done, FIELD_MAX), clean(merged, FIELD_MAX),
            clean(waiting, FIELD_MAX), clean(problems, FIELD_MAX))


@mcp.tool()
def write_cycle_report(title: str, done: str = "", merged: str = "", waiting: str = "",
                       problems: str = "") -> dict:
    """Записать сводку цикла автономной работы. В бот она уйдёт в течение 15 минут.

    title — «Цикл 19.10 14:00» (приставка «Listing Suite · » добавится сама);
    done — что сделано; merged — что смержено само (уровень «сам»);
    waiting — что ждёт владельца («мержи #N», ответ, секрет); problems — что не получилось.
    Пустые поля в сообщение не попадают."""
    try:
        values = row(title, done, merged, waiting, problems)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    dsn = os.environ.get("LAKEBASE_DSN")
    if not dsn:
        return {"ok": False, "error": "у сервера ls-cycle-report нет LAKEBASE_DSN — его подключение заводит владелец (docs/autonomy.md, «Как включить»)"}
    # Сбой ПОДКЛЮЧЕНИЯ наружу идёт без текста драйвера: libpq цитирует в нём куски строки подключения,
    # и при неверно закодированном пароле в ответ агенту ушёл бы пароль целиком
    # («invalid percent-encoded token: "<пароль>"» — проверено проверяющим PR #140).
    try:
        con = psycopg2.connect(dsn, connect_timeout=20)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"подключиться не удалось ({type(e).__name__}"
                                      f"{', код ' + e.pgcode if getattr(e, 'pgcode', None) else ''}); "
                                      "текст драйвера не показывается — в нём бывает строка подключения. "
                                      "Проверить подключение сервера ls-cycle-report у владельца "
                                      "(пароль в URI — процентным кодированием)"}
    try:
        with con, con.cursor() as cur:
            cur.execute(INSERT_SQL, values)
    except Exception as e:  # noqa: BLE001 — наружу первая строка, без трассировки
        first = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        return {"ok": False, "error": scrub(first, dsn)}
    finally:
        con.close()
    return {"ok": True, "title": values[0]}


def secret_parts(dsn: str) -> list[str]:
    """Пароль из строки подключения в обеих формах (URI и key=value), как есть и раскодированный."""
    found = re.findall(r"://[^:/@\s]+:([^@\s]+)@", dsn) + re.findall(r"\bpassword\s*=\s*'?([^'\s]+)", dsn)
    return sorted({p for v in found for p in (v, unquote(v)) if len(p) >= 4}, key=len, reverse=True)


def scrub(text: str, dsn: str) -> str:
    """Страховка для ошибок запроса: в них строки подключения быть не должно, но если вдруг — не наружу."""
    for part in secret_parts(dsn):
        text = text.replace(part, "<скрыто>")
    return text


if __name__ == "__main__":
    mcp.run()
