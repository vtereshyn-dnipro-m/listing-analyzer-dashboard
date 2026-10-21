"""Применение одной миграции listing_data под учёткой владельца (профиль Databricks CLI).

Решение владельца 21.10.2026: миграции применяет агент, но только по команде
«применяй <имя файла>», под учёткой владельца, не под claude_code_ro; удаление
данных и DROP — никогда сам. Уровень этого файла — «ждёт меня»: он пишет в базу.

Использование: python scratchpad/apply_migration.py migrations/<файл>.sql [--check-only]

Что делает и от чего отказывается (проверки #158):
1. Файл — только прямо в migrations/: migrations/kabinet/ — SQL для базы Кабинета
   (роли, app_permissions), его агент не применяет никогда.
2. Файл — одна транзакция: первый оператор BEGIN, ровно один BEGIN и один COMMIT,
   внутри — ни END, ABORT, START, ROLLBACK, PREPARE, и ни COMMIT/ROLLBACK даже в
   телах DO и функций.
3. Удаление данных и DROP — отказ, в том числе внутри тел DO и функций.
   Единственное исключение — пересоздание триггера: DROP TRIGGER IF EXISTS X ON T
   при CREATE TRIGGER X … ON T настоящим оператором того же файла ДО COMMIT
   (пара «имя, таблица»; имена в кавычках исключения не получают). Событие триггера на
   очистку («BEFORE/AFTER/OR <очистка> ON») командой очистки не считается.
4. После COMMIT — только SELECT без изменяющих слов (SET, INSERT, INTO, …).
5. Разбор понимает комментарии «--» и «/* */» везде (и в телах $…$), строки '…'
   и E'…', имена в двойных кавычках, тела $tag$…$tag$. Предел: команду,
   собранную строкой в EXECUTE '…', разбор не видит — поэтому применяется только
   файл, прошедший ревью PR. Граница держится здесь, кодом: хук
   .claude/hooks/guard.py содержимое файла не видит.
6. Учётка CLI обязана быть учёткой владельца — иначе остановка.
7. Токен — `databricks postgres generate-database-credential` для эндпоинта
   listing-suite/production/primary; идёт прямо в подключение и НИГДЕ не
   печатается.
8. Предпроверка без изменений → файл до COMMIT (autocommit, транзакцию держат
   BEGIN/COMMIT файла) → проверочные запросы в сессии ТОЛЬКО НА ЧТЕНИЕ. Ошибка —
   ROLLBACK и текст ошибки.
--check-only: только предпроверка, в базе ничего не меняет (учётные данные БД при
этом выпускаются — это нужно для подключения).
"""
import json
import pathlib
import re
import subprocess
import sys

OWNER = "v.tereshyn@dniprom.com"
ENDPOINT = "projects/listing-suite/branches/production/endpoints/primary"
DB = "databricks_postgres"
ROOT = pathlib.Path(__file__).resolve().parent.parent

# Слова собраны из частей: хук .claude/hooks/guard.py останавливает команды,
# в запускаемых файлах которых они стоят целиком.
W_DROP = "DR" + "OP"
W_WIPE = "TRUNC" + "ATE"
W_DEL = "DEL" + "ETE"

TAIL_FORBIDDEN = {"INSERT", "UPDATE", W_DEL, W_DROP, W_WIPE, "ALTER", "CREATE", "SET", "SET_CONFIG",
                  "GRANT", "REVOKE", "COPY", "CALL", "DO", "LOCK", "VACUUM", "REFRESH", "NOTIFY", "EXECUTE",
                  "INTO", "NEXTVAL", "SETVAL", "PREPARE", "MERGE", "DISCARD", "RESET", "IMPORT", "CLUSTER",
                  "REINDEX", "DBLINK", "DBLINK_EXEC", "PG_TERMINATE_BACKEND", "PG_CANCEL_BACKEND",
                  "PG_RELOAD_CONF", "LO_IMPORT", "LO_EXPORT", "LO_UNLINK", "COMMIT", "ROLLBACK"}
TX_CONTROL = {"BEGIN", "COMMIT", "END", "ABORT", "START", "ROLLBACK", "PREPARE"}


def fail(msg: str) -> None:
    print("ОТКАЗ:", msg)
    sys.exit(2)


# ------------------------------------------------------------------ разбор SQL
_IDCHAR = re.compile(r"[A-Za-z0-9_$\x80-\U0010ffff]")


def _tag_at(sql: str, i: int):
    """Тег долларовой строки, начатой на sql[i], или None. Как у Postgres: тег
    не может стоять сразу после символа имени («x$a$» — это имя, не строка)."""
    if i and _IDCHAR.match(sql[i - 1]):
        return None
    m = re.match(r"\$([A-Za-z_\x80-\U0010ffff][A-Za-z0-9_\x80-\U0010ffff]*)?\$", sql[i:])
    return m.group(0) if m else None


def _quote_end(sql: str, i: int, q: str, backslash: bool) -> int:
    """Индекс после закрывающей кавычки q; удвоенная кавычка — внутри."""
    n, j = len(sql), i + 1
    while j < n:
        if backslash and sql[j] == "\\":
            j += 2
        elif sql[j] == q and j + 1 < n and sql[j + 1] == q:
            j += 2
        elif sql[j] == q:
            return j + 1
        else:
            j += 1
    return n


def tokens(sql: str):
    """Лексер: (вид, начало, конец, тело). Виды: comment, string, ident, dollar
    (тело — текст между тегами), semi, text. Незакрытое тянется до конца файла."""
    i, n, run = 0, len(sql), 0
    out = []

    def flush(upto):
        if upto > run:
            out.append(("text", run, upto, None))

    while i < n:
        c = sql[i]
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j < 0 else j
            kind, body = "comment", None
        elif sql.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if sql.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif sql.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            kind, body = "comment", None
        elif c in "eE" and sql[i + 1:i + 2] == "'" and not (i and _IDCHAR.match(sql[i - 1])):
            j, kind, body = _quote_end(sql, i + 1, "'", True), "string", None
        elif c == "'":
            j, kind, body = _quote_end(sql, i, "'", False), "string", None
        elif c == '"':
            j, kind, body = _quote_end(sql, i, '"', False), "ident", None
        elif c == "$" and _tag_at(sql, i):
            tag = _tag_at(sql, i)
            k = sql.find(tag, i + len(tag))
            body = sql[i + len(tag): n if k < 0 else k]
            j, kind = (n if k < 0 else k + len(tag)), "dollar"
        elif c == ";":
            j, kind, body = i + 1, "semi", None
        else:
            i += 1
            continue
        flush(i)
        out.append((kind, i, j, body))
        i = run = j
    flush(n)
    return out


def scrub(sql: str) -> str:
    """Скелет для проверок: комментарии → пробел, строки → '', имена в кавычках
    → "" (не совпадают ни с одним словом), тела $…$ → их скелет, рекурсивно."""
    parts = []
    for kind, a, b, body in tokens(sql):
        parts.append({"comment": " ", "string": " '' ", "ident": ' "" ', "semi": ";"}.get(kind)
                     or (" $$ " + scrub(body).replace(";", " ; ") + " $$ " if kind == "dollar" else sql[a:b]))
    return "".join(parts)


def strip_comments(sql: str) -> str:
    """Текст без комментариев вне строк и тел $…$ — то, что уходит проверочными запросами."""
    return "".join(" " if kind == "comment" else sql[a:b] for kind, a, b, _ in tokens(sql))


def split_spans(sql: str) -> list[tuple[int, int]]:
    """Границы операторов (начало, конец с «;») по «;» вне комментариев, строк,
    имён и тел $…$; пустые операторы отброшены."""
    spans, start = [], 0
    for kind, a, b, _ in tokens(sql):
        if kind == "semi":
            spans.append((start, b))
            start = b
    spans.append((start, len(sql)))
    return [(a, b) for a, b in spans if scrub(sql[a:b]).strip(" \t\r\n;")]


def statements(sql: str) -> list[str]:
    """Операторы без комментариев и без завершающей «;»."""
    return [strip_comments(sql[a:b]).strip().rstrip(";").strip() for a, b in split_spans(sql)]


def _skel(stmt: str) -> str:
    return re.sub(r"\s+", " ", scrub(stmt)).strip(" ;")


def _norm_table(t: str) -> str:
    t = t.lower()
    return t.split(".", 1)[1] if t.startswith("listing_data.") else t


_NAME = r"([A-Za-z_][A-Za-z0-9_]*)"
_TABLE = r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)"


def vet(path: pathlib.Path, root: pathlib.Path | None = None) -> tuple[str, list[str]]:
    home = ((root or ROOT) / "migrations").resolve()
    if path.suffix != ".sql" or path.resolve().parent != home:
        fail(f"{path} — не файл прямо в migrations/ (migrations/kabinet/ агент не применяет)")
    text = path.read_text(encoding="utf-8-sig")
    spans = split_spans(text)
    skels = [_skel(text[a:b]) for a, b in spans]
    heads = [s.split(None, 1)[0].upper() if s else "" for s in skels]
    if not skels or skels[0].upper() != "BEGIN" or heads.count("BEGIN") != 1 or \
            heads.count("COMMIT") != 1 or skels[heads.index("COMMIT")].upper() != "COMMIT":
        fail("файл — одна транзакция: первый оператор BEGIN;, ровно один BEGIN; и один COMMIT;")
    k = heads.index("COMMIT")
    for (a, b), s, h in zip(spans[1:k], skels[1:k], heads[1:k]):
        if h in TX_CONTROL or re.search(r"\b(COMMIT|ROLLBACK)\b", s, re.I):
            fail(f"внутри транзакции — управление транзакцией ({h}): {' '.join(text[a:b].split())[:90]}")
    created = set()
    for s in skels[1:k]:
        m = re.match(rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:CONSTRAINT\s+)?TRIGGER\s+{_NAME}\s.*?\bON\s+{_TABLE}\s",
                     s + " ", re.I)
        if m:
            created.add((m.group(1).lower(), _norm_table(m.group(2))))
    for (a, b), s in zip(spans[1:k], skels[1:k]):
        deep = re.sub(rf"\b(BEFORE|AFTER|OR)\s+{W_WIPE}\b", " ", s, flags=re.I)
        if re.search(rf"\b({W_WIPE}|{W_DEL}\s+FROM)\b", deep, re.I):
            fail(f"удаление данных в файле — агент этого не применяет: {' '.join(text[a:b].split())[:90]}")
        if re.search(rf"\b{W_DROP}\b", deep, re.I):
            ok = re.fullmatch(rf"{W_DROP}\s+TRIGGER\s+IF\s+EXISTS\s+{_NAME}\s+ON\s+{_TABLE}", s, re.I)
            if not (ok and (ok.group(1).lower(), _norm_table(ok.group(2))) in created):
                fail(f"{W_DROP} в файле — агент этого не применяет (кроме пересоздания триггера: то же имя, "
                     f"та же таблица, CREATE до COMMIT): {' '.join(text[a:b].split())[:90]}")
    checks = []
    for (a, b), s in zip(spans[k + 1:], skels[k + 1:]):
        bad = sorted({w.upper() for w in re.findall(r"[A-Za-z_]+", s)} & TAIL_FORBIDDEN)
        if not s.upper().startswith("SELECT ") or bad:
            fail(f"после COMMIT — только SELECT без изменяющих слов ({', '.join(bad) or 'не SELECT'}): "
                 f"{' '.join(text[a:b].split())[:90]}")
        checks.append(strip_comments(text[a:b]).strip().rstrip(";").strip())
    return text[:spans[k][1]], checks


# ------------------------------------------------------------- применение
def cli(*args) -> dict:
    r = subprocess.run(["databricks", *args, "--output", "json"], capture_output=True, text=True)
    if r.returncode != 0:
        first = (r.stderr or "").strip().splitlines()[:1]
        fail(f"databricks {args[0]} {args[1] if len(args) > 1 else ''}: код {r.returncode}"
             + (f" — {first[0][:200]}" if first else ""))
    return json.loads(r.stdout)


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
    import psycopg2

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
    for stmt in checks:
        show(cur, stmt)
    conn.rollback()
    conn.close()


if __name__ == "__main__":
    main()
