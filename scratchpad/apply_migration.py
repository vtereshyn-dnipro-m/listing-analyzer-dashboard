"""Применение одной миграции listing_data под учёткой владельца (профиль Databricks CLI).

Использование: python apply_migration.py <путь к .sql> [--check-only]

1. Токен — `databricks postgres generate-database-credential` для эндпоинта
   listing-suite/production/primary под профилем CLI владельца. Токен идёт прямо
   в подключение и НИГДЕ не печатается.
2. Предпроверка без изменений: кто подключён, какая база, что уже есть.
3. Файл — до последнего COMMIT включительно, одной строкой: его BEGIN/COMMIT
   держат транзакцию (autocommit, чтобы драйвер не открыл свою).
4. Проверочные запросы — то, что после COMMIT, по одному, с выводом результата.
Ошибка до COMMIT — ROLLBACK и текст ошибки.
"""
import json
import subprocess
import sys

import psycopg2

ENDPOINT = "projects/listing-suite/branches/production/endpoints/primary"
DB = "databricks_postgres"


def creds():
    me = json.loads(subprocess.run(["databricks", "current-user", "me", "--output", "json"],
                                   check=True, capture_output=True, text=True).stdout)["userName"]
    ep = json.loads(subprocess.run(["databricks", "postgres", "get-endpoint", ENDPOINT, "--output", "json"],
                                   check=True, capture_output=True, text=True).stdout)
    host = (ep.get("status") or {}).get("hosts", {}).get("host")
    tok = json.loads(subprocess.run(["databricks", "postgres", "generate-database-credential", ENDPOINT,
                                     "--output", "json"], check=True, capture_output=True, text=True).stdout)["token"]
    return me, host, tok


def show(cur, sql):
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall() if cur.description else []
    print("  SQL:", " ".join(sql.split())[:110])
    for r in rows:
        print("   ", dict(zip(cols, r)))
    if not rows:
        print("    (нет строк)")


def main():
    path = sys.argv[1]
    check_only = "--check-only" in sys.argv
    me, host, tok = creds()
    print(f"учётка CLI: {me} | эндпоинт: {ENDPOINT} | база: {DB}")
    conn = psycopg2.connect(host=host, dbname=DB, user=me, password=tok, sslmode="require",
                            connect_timeout=60, application_name="listing-suite-migration")
    del tok
    conn.autocommit = True
    cur = conn.cursor()
    print("предпроверка:")
    show(cur, """SELECT current_user, current_database(),
                        to_regclass('listing_data.passport_source_artifacts')::text AS passports,
                        to_regclass('listing_data.content_versions')::text AS content""")
    if check_only:
        return
    text = open(path, encoding="utf-8").read()
    cut = text.rfind("COMMIT;") + len("COMMIT;")
    body, checks = text[:cut], text[cut:]
    print(f"применяю {path.split('/')[-1]} ...")
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
    print("проверочные запросы из файла:")
    code = "\n".join(line.split("--")[0] for line in checks.splitlines())
    for stmt in [s.strip() for s in code.split(";") if s.strip()]:
        show(cur, stmt)
    conn.close()


if __name__ == "__main__":
    main()
