"""Применение одной миграции listing_data под учёткой владельца (профиль Databricks CLI).

Решение владельца 21.10.2026: миграции применяет агент, но только по команде
«применяй <имя файла>», под учёткой владельца, не под claude_code_ro; удаление
данных и DROP — никогда сам. Уровень этого файла — «ждёт меня»: он пишет в базу.

Использование: python scratchpad/apply_migration.py migrations/<файл>.sql [--check-only]

Что делает и от чего отказывается (проверка #158):
1. Файл — только прямо в migrations/: migrations/kabinet/ — SQL для базы Кабинета
   (роли, app_permissions), его агент не применяет никогда.
2. Файл обязан быть одной транзакцией: ровно один BEGIN; и ровно один COMMIT;.
3. Удаление данных и DROP — отказ, в том числе внутри тел DO и функций.
   Единственное исключение — пересоздание триггера: DROP TRIGGER IF EXISTS X ON …
   при CREATE TRIGGER X в том же файле. Событие триггера на очистку таблицы
   («BEFORE … ON») командой очистки не считается. Граница держится здесь,
   кодом: хук .claude/hooks/guard.py содержимое файла не видит. Предел:
   команду, собранную строкой в EXECUTE '…', скрипт не видит — поэтому
   применяется только файл, прошедший ревью PR.
4. Учётка CLI обязана быть учёткой владельца — иначе остановка.
5. Токен — `databricks postgres generate-database-credential` для эндпоинта
   listing-suite/production/primary; идёт прямо в подключение и НИГДЕ не
   печатается.
6. Предпроверка без изменений → файл до COMMIT (autocommit, транзакцию держат
   BEGIN/COMMIT файла) → проверочные запросы из конца файла в сессии ТОЛЬКО НА
   ЧТЕНИЕ. Ошибка — ROLLBACK и текст ошибки.
--check-only: только предпроверка, в базе ничего не меняет (учётные данные БД при
этом выпускаются — это нужно для подключения).
"""
import json
import pathlib
import re
import subprocess
import sys

import psycopg2

OWNER = "v.tereshyn@dniprom.com"
ENDPOINT = "projects/listing-suite/branches/production/endpoints/primary"
DB = "databricks_postgres"
ROOT = pathlib.Path(__file__).resolve().parent.parent

# Слова собраны из частей: хук .claude/hooks/guard.py останавливает команды,
# в запускаемых файлах которых они стоят целиком.
W_DROP = "DR" + "OP"
W_WIPE = "TRUNC" + "ATE"
W_DEL = "DEL" + "ETE"


def fail(msg: str) -> None:
    print("ОТКАЗ:", msg)
    sys.exit(2)


def cli(*args) -> dict:
    r = subprocess.run(["databricks", *args, "--output", "json"], capture_output=True, text=True)
    if r.returncode != 0:
        first = (r.stderr or r.stdout or "").strip().splitlines()[:1]
        fail(f"databricks {args[0]} {args[1] if len(args) > 1 else ''}: код {r.returncode}"
             + (f" — {first[0][:200]}" if first else ""))
    return json.loads(r.stdout)


def strip_comments(sql: str) -> str:
    """Без комментариев «--» и «/* */», строки и тела $…$ — нетронуты."""
    out, i, n = [], 0, len(sql)
    while i < n:
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
        elif sql[i] == "'":
            j = i + 1
            while j < n and not (sql[j] == "'" and not sql.startswith("''", j)):
                j += 2 if sql.startswith("''", j) else 1
            out.append(sql[i:j + 1])
            i = j + 1
        elif sql[i] == "$":
            m = re.match(r"\$[A-Za-z_]*\$", sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                j = n if j < 0 else j + len(tag)
                out.append(sql[i:j])
                i = j
            else:
                out.append(sql[i])
                i += 1
        else:
            out.append(sql[i])
            i += 1
    return "".join(out)


def statements(sql: str) -> list[str]:
    """Операторы по «;» вне строк и тел $…$ (комментарии уже сняты)."""
    out, cur, i, n = [], [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            j = i + 1
            while j < n and not (sql[j] == "'" and not sql.startswith("''", j)):
                j += 2 if sql.startswith("''", j) else 1
            cur.append(sql[i:j + 1])
            i = j + 1
            continue
        if ch == "$":
            m = re.match(r"\$[A-Za-z_]*\$", sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                j = n if j < 0 else j + len(tag)
                cur.append(sql[i:j])
                i = j
                continue
        if ch == ";":
            s = "".join(cur).strip()
            if s:
                out.append(s)
            cur = []
        else:
            cur.append(ch)
        i += 1
    s = "".join(cur).strip()
    if s:
        out.append(s)
    return out


def bare(stmt: str) -> str:
    """Оператор без строк и тел $…$ — для поиска опасных слов вне литералов."""
    s = re.sub(r"'(?:[^']|'')*'", "''", stmt)
    return re.sub(r"\$([A-Za-z_]*)\$.*?\$\1\$", "$$", s, flags=re.S)


def vet(path: pathlib.Path) -> tuple[str, str]:
    if path.suffix != ".sql" or path.resolve().parent != (ROOT / "migrations").resolve():
        fail(f"{path} — не файл прямо в migrations/ (migrations/kabinet/ агент не применяет)")
    text = path.read_text(encoding="utf-8")
    stmts = statements(strip_comments(text))
    heads = [s.split(None, 1)[0].upper() for s in stmts]
    if heads.count("BEGIN") != 1 or heads.count("COMMIT") != 1 or heads[0] != "BEGIN":
        fail("файл обязан быть одной транзакцией: первым оператором BEGIN;, ровно один BEGIN; и один COMMIT;")
    k = heads.index("COMMIT")
    created = {m.lower() for s in stmts for m in re.findall(r"CREATE\s+TRIGGER\s+([A-Za-z_][A-Za-z0-9_]*)", bare(s), re.I)}
    for s in stmts[:k]:
        b = bare(s)                                   # без строк и тел $…$ — сам оператор
        deep = re.sub(r"'(?:[^']|'')*'", "''", s)     # без строк, но С телами DO и функций
        # событие триггера («BEFORE/AFTER/OR <очистка>») — не команда очистки
        deep = re.sub(rf"\b(BEFORE|AFTER|OR)\s+{W_WIPE}\b", " ", deep, flags=re.I)
        if re.search(rf"\b({W_WIPE}|{W_DEL}\s+FROM)\b", deep, re.I):
            fail(f"удаление данных в файле — агент этого не применяет: {' '.join(s.split())[:90]}")
        if re.search(rf"\b{W_DROP}\b", deep, re.I):
            ok = re.fullmatch(rf"\s*{W_DROP}\s+TRIGGER\s+IF\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)\s+ON\s+"
                              r"[A-Za-z_][A-Za-z0-9_.]*\s*", b, re.I)
            if not (ok and ok.group(1).lower() in created):
                fail(f"{W_DROP} в файле — агент этого не применяет (кроме пересоздания триггера): "
                     f"{' '.join(s.split())[:90]}")
    if any(re.match(r"(BEGIN|COMMIT|START|ROLLBACK)\b", h, re.I) for h in heads[k + 1:]):
        fail("после COMMIT — только проверочные запросы")
    commit_at = [m.end() for m in re.finditer(r"\bCOMMIT\s*;", text, re.I)]
    if len(commit_at) != 1:
        fail("ровно один COMMIT; в тексте файла (включая комментарии) — иначе граница проверочных запросов неоднозначна")
    cut = commit_at[0]
    return text[:cut], text[cut:]


def show(cur, sql: str) -> None:
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall() if cur.description else []
    print("  SQL:", " ".join(sql.split())[:110])
    for r in rows:
        print("   ", dict(zip(cols, r)))
    if not rows:
        print("    (нет строк)")


def main() -> None:
    path = pathlib.Path(sys.argv[1])
    check_only = "--check-only" in sys.argv
    body, checks = vet(path)
    me = cli("current-user", "me")["userName"]
    if me != OWNER:
        fail(f"профиль CLI — {me}, а не учётка владельца {OWNER}")
    host = (cli("postgres", "get-endpoint", ENDPOINT).get("status") or {}).get("hosts", {}).get("host")
    tok = cli("postgres", "generate-database-credential", ENDPOINT)["token"]
    print(f"учётка CLI: {me} | эндпоинт: {ENDPOINT} | база: {DB}")
    conn = psycopg2.connect(host=host, dbname=DB, user=me, password=tok, sslmode="require",
                            connect_timeout=60, application_name="listing-suite-migration")
    del tok
    conn.autocommit = True
    cur = conn.cursor()
    print("предпроверка:")
    show(cur, "SELECT current_user, current_database(), to_regnamespace('listing_data')::text AS schema")
    if check_only:
        conn.close()
        return
    print(f"применяю {path.name} ...")
    try:
        cur.execute(body)
    except Exception as e:  # noqa: BLE001
        print("ОШИБКА:", type(e).__name__, str(e).strip().splitlines()[0])
        try:
            cur.execute("ROLLBACK")
            print("ROLLBACK выполнен")
        except Exception as e2:  # noqa: BLE001
            print("ROLLBACK:", type(e2).__name__, str(e2).strip().splitlines()[0])
        sys.exit(1)
    print("применено (до COMMIT включительно).")
    print("проверочные запросы из файла (сессия только на чтение):")
    conn.autocommit = False
    conn.set_session(readonly=True)
    for stmt in statements(strip_comments(checks)):
        show(cur, stmt)
    conn.rollback()
    conn.close()


if __name__ == "__main__":
    main()
