# -*- coding: utf-8 -*-
"""
tests/test_apply_migration.py — `scratchpad/apply_migration.py` отказывает там,
где обязан (решение владельца 21.10.2026, проверки #158). Без базы и без сети:
проверяется только `vet()` и разбор SQL. В настоящую папку migrations/ тест
ничего не пишет: пробные файлы лежат во временном корне.

Что заперто:
  · применяется только файл прямо в migrations/ — кабинетный SQL
    (migrations/kabinet/: роли и app_permissions) скрипт не применяет никогда;
  · файл — одна транзакция: первым BEGIN;, ровно один BEGIN; и один COMMIT;,
    внутри ни END, ABORT, START, ROLLBACK, PREPARE, ни COMMIT в теле DO;
  · удаление данных и DROP — отказ, в том числе в телах DO и функций;
    исключение одно — пересоздание триггера: то же имя на той же таблице,
    CREATE настоящим оператором ПОСЛЕ DROP и до COMMIT, таблица только
    listing_data.<имя>, без RENAME и SET SCHEMA в том же файле;
  · после COMMIT — только SELECT без изменяющих слов;
  · разбор не обманывается комментариями в телах $…$, именами "a'b",
    строками E'\\'', вложенными $q$…$q$ и именами вида x$a$;
  · уже применённые миграции content_versions проходят vet().

Запуск (pytest не нужен):  python tests/test_apply_migration.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAILS: list[str] = []
D = "DR" + "OP"          # слова собраны из частей: хук .claude/hooks/guard.py
WIPE = "TRUNC" + "ATE"   # читает запускаемые файлы целиком
DEL = "DEL" + "ETE"


def check(name: str, cond) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


spec = importlib.util.spec_from_file_location("apply_migration", ROOT / "scratchpad" / "apply_migration.py")
am = importlib.util.module_from_spec(spec)
spec.loader.exec_module(am)


def verdict(path: pathlib.Path, root: pathlib.Path | None = None):
    """True — пропущен, False — отказ (код 2), иначе — исключение как есть."""
    try:
        am.vet(path, root)
        return True
    except SystemExit as e:
        return False if e.code == 2 else e


MIG = ROOT / "migrations"
for name in ("2026-10-21_content_versions.sql", "2026-10-21_content_versions_checks.sql",
             "2026-10-21_passport_copy_frozen.sql"):
    if (MIG / name).exists():
        check(f"vet пропускает {name}", verdict(MIG / name) is True)

kab = sorted((MIG / "kabinet").glob("*.sql"))
check(f"кабинетный SQL — отказ всегда ({len(kab)} файла)", kab and all(verdict(p) is False for p in kab))

TMP = pathlib.Path(tempfile.mkdtemp())
try:
    (TMP / "migrations" / "kabinet").mkdir(parents=True)
    ok_sql = "BEGIN;\nSELECT 1;\nCOMMIT;\n"
    for rel in ("migrations/kabinet/x.sql", "x.sql"):
        (TMP / rel).write_text(ok_sql, encoding="utf-8")
    (TMP / "migrations" / "x.txt").write_text(ok_sql, encoding="utf-8")
    check("тот же файл прямо в migrations/ — пропуск (контроль)",
          (TMP / "migrations" / "y.sql").write_text(ok_sql, encoding="utf-8") and
          verdict(TMP / "migrations" / "y.sql", TMP) is True)
    check("файл во вложенной папке migrations/ — отказ", verdict(TMP / "migrations/kabinet/x.sql", TMP) is False)
    check("файл вне migrations/ — отказ", verdict(TMP / "x.sql", TMP) is False)
    check("не .sql — отказ", verdict(TMP / "migrations" / "x.txt", TMP) is False)
    check("временный корень не принят за настоящий", verdict(TMP / "migrations" / "y.sql") is False)

    TRG = "CREATE TRIGGER tg BEFORE UPDATE ON listing_data.t FOR EACH ROW EXECUTE FUNCTION f();\n"
    DROPTRG = f"{D} TRIGGER IF EXISTS tg ON listing_data.t;\n"
    CASES = [
        # --- нормальные файлы
        (True, "одна транзакция с CREATE", "BEGIN;\nCREATE TABLE IF NOT EXISTS listing_data.t (id int);\nCOMMIT;\nSELECT 1;\n"),
        (True, "BOM в начале файла", "\ufeffBEGIN;\nSELECT 1;\nCOMMIT;\n"),
        (True, "пересоздание триггера", f"BEGIN;\n{DROPTRG}{TRG}COMMIT;\n"),
        (False, "пересоздание: таблица без схемы в DROP", f"BEGIN;\n{D} TRIGGER IF EXISTS tg ON t;\n{TRG}COMMIT;\n"),
        (False, "пересоздание: таблица без схемы в обоих",
         f"BEGIN;\n{D} TRIGGER IF EXISTS tg ON t;\nCREATE TRIGGER tg BEFORE UPDATE ON t FOR EACH ROW EXECUTE FUNCTION f();\nCOMMIT;\n"),
        (False, "пересоздание и SET search_path — CREATE ушёл бы на чужую t",
         f"BEGIN;\n{D} TRIGGER IF EXISTS tg ON t;\nSET LOCAL search_path = other;\n"
         "CREATE TRIGGER tg BEFORE UPDATE ON t FOR EACH ROW EXECUTE FUNCTION f();\nCOMMIT;\n"),
        (False, "пересоздание и RENAME — прежняя таблица осталась бы без триггера",
         f"BEGIN;\n{DROPTRG}ALTER TABLE listing_data.t RENAME TO t_old;\n"
         f"CREATE TABLE listing_data.t (id int);\n{TRG}COMMIT;\n"),
        (False, "пересоздание и SET SCHEMA — прежняя таблица ушла бы без триггера",
         f"BEGIN;\n{DROPTRG}ALTER TABLE listing_data.t SET SCHEMA archive;\n"
         f"CREATE TABLE listing_data.t (id int);\n{TRG}COMMIT;\n"),
        (False, "пересоздание и SET SCHEMA внутри DO",
         f"BEGIN;\n{DROPTRG}DO $$ BEGIN ALTER TABLE listing_data.t SET SCHEMA archive; END $$;\n"
         f"CREATE TABLE listing_data.t (id int);\n{TRG}COMMIT;\n"),
        (True, "RENAME без пересоздания триггера — не наше дело", "BEGIN;\nALTER TABLE listing_data.t RENAME COLUMN a TO b;\nCOMMIT;\n"),
        (True, f"защитный триггер BEFORE {WIPE} — не очистка",
         f"BEGIN;\nCREATE TRIGGER nw BEFORE {WIPE} ON listing_data.t FOR EACH STATEMENT EXECUTE FUNCTION f();\nCOMMIT;\n"),
        (True, f"слово {D} внутри строки — не оператор", f"BEGIN;\nCOMMENT ON TABLE listing_data.t IS 'no {D} here';\nCOMMIT;\n"),
        (True, f"слово {D} в комментарии — не оператор", f"BEGIN;\n-- {D} TABLE в комментарии\nSELECT 1;\nCOMMIT;\n"),
        (True, f"{DEL} во вложенном комментарии /* /* */ */",
         f"BEGIN;\n/* a /* b */ {DEL} FROM listing_data.t; */\nSELECT 1;\nCOMMIT;\n"),
        (True, "после COMMIT: слова в строках и CASE … END",
         "BEGIN;\nSELECT 1;\nCOMMIT;\nSELECT has_table_privilege('x', 'listing_data.t', 'UPDATE') AS u, "
         "CASE WHEN true THEN 1 END AS c;\n"),
        (True, "имена x$a$ и y$a$ — не тело $…$, COMMIT виден",
         "BEGIN;\nCREATE TABLE listing_data.x$a$ (id int);\nCOMMIT;\nSELECT 1 AS y$a$;\n"),
        # --- одна транзакция
        (False, "без BEGIN", "CREATE TABLE listing_data.t (id int);\n"),
        (False, "без COMMIT", "BEGIN;\nCREATE TABLE listing_data.t (id int);\n"),
        (False, "BEGIN не первым", "SELECT 1;\nBEGIN;\nSELECT 1;\nCOMMIT;\n"),
        (False, "два COMMIT", "BEGIN;\nSELECT 1;\nCOMMIT;\nBEGIN;\nSELECT 2;\nCOMMIT;\n"),
        (False, "commit строчными — тоже считается, и второй — отказ", "BEGIN;\ncommit;\nCOMMIT;\n"),
        (False, "COMMIT AND CHAIN", "BEGIN;\nSELECT 1;\nCOMMIT AND CHAIN;\n"),
        (False, "END внутри", "BEGIN;\nSELECT 1;\nEND;\nCREATE TABLE listing_data.t (id int);\nCOMMIT;\n"),
        (False, "ABORT внутри", "BEGIN;\nABORT;\nSELECT 1;\nCOMMIT;\n"),
        (False, "ROLLBACK внутри", "BEGIN;\nROLLBACK;\nSELECT 1;\nCOMMIT;\n"),
        (False, "START TRANSACTION внутри", "BEGIN;\nSTART TRANSACTION;\nSELECT 1;\nCOMMIT;\n"),
        (False, "PREPARE TRANSACTION внутри", "BEGIN;\nPREPARE TRANSACTION 'x';\nCOMMIT;\n"),
        (False, "COMMIT внутри тела DO", "BEGIN;\nDO $$ BEGIN COMMIT; END $$;\nCOMMIT;\n"),
        # --- тела строкой (проверка #160): разбор видит их пустыми
        (False, f"{DEL} в теле функции строкой AS '…'",
         f"BEGIN;\nCREATE FUNCTION listing_data.g() RETURNS void LANGUAGE sql AS '{DEL} FROM listing_data.t';\n"
         "SELECT listing_data.g();\nCOMMIT;\n"),
        (False, f"{D} TABLE в теле функции E-строкой",
         f"BEGIN;\nCREATE OR REPLACE FUNCTION listing_data.g() RETURNS void LANGUAGE sql AS E'{D} TABLE listing_data.t';\nCOMMIT;\n"),
        (False, "RENAME в теле функции строкой при пересоздании триггера",
         f"BEGIN;\n{D} TRIGGER IF EXISTS tg ON listing_data.t;\nCREATE FUNCTION listing_data.g() RETURNS void LANGUAGE sql AS "
         "'ALTER TABLE listing_data.t RENAME TO t_old';\nSELECT listing_data.g();\nCREATE TABLE listing_data.t (id int);\n"
         "CREATE TRIGGER tg BEFORE UPDATE ON listing_data.t FOR EACH ROW EXECUTE FUNCTION f();\nCOMMIT;\n"),
        (False, "тело процедуры строкой", "BEGIN;\nCREATE PROCEDURE listing_data.p() LANGUAGE sql AS 'SELECT 1';\nCOMMIT;\n"),
        (False, "тело строкой, LANGUAGE после AS",
         "BEGIN;\nCREATE FUNCTION listing_data.g() RETURNS void AS 'SELECT 1' LANGUAGE sql;\nCOMMIT;\n"),
        (False, "C-функция AS 'obj', 'sym'",
         "BEGIN;\nCREATE FUNCTION listing_data.g() RETURNS void AS 'lib', 'sym' LANGUAGE c;\nCOMMIT;\n"),
        (False, "комментарий и перевод строки между AS и строкой, строчными",
         "BEGIN;\ncreate or replace function listing_data.g() returns void language sql as /* x */\n-- y\n'select 1';\nCOMMIT;\n"),
        (False, "DO строкой", f"BEGIN;\nDO '{DEL} FROM listing_data.t';\nCOMMIT;\n"),
        (False, "DO LANGUAGE plpgsql строкой", "BEGIN;\nDO LANGUAGE plpgsql 'BEGIN NULL; END';\nCOMMIT;\n"),
        (True, "тело функции $$…$$ со строками внутри",
         "BEGIN;\nCREATE FUNCTION listing_data.g() RETURNS text LANGUAGE sql AS $$ SELECT 'AS ''x''' $$;\nCOMMIT;\n"),
        (True, "COMMENT ON FUNCTION … IS '…' — не тело",
         "BEGIN;\nCOMMENT ON FUNCTION listing_data.g() IS 'AS тело';\nCOMMIT;\n"),
        # --- удаление данных и DROP
        (False, f"{D} TABLE", f"BEGIN;\n{D} TABLE listing_data.t;\nCOMMIT;\n"),
        (False, f"{D} COLUMN", f"BEGIN;\nALTER TABLE listing_data.t {D} COLUMN x;\nCOMMIT;\n"),
        (False, f"{D} FUNCTION", f"BEGIN;\n{D} FUNCTION listing_data.f();\nCOMMIT;\n"),
        (False, f"{DEL} FROM", f"BEGIN;\n{DEL} FROM listing_data.t WHERE id = 1;\nCOMMIT;\n"),
        (False, WIPE, f"BEGIN;\n{WIPE} listing_data.t;\nCOMMIT;\n"),
        (False, f"{DEL} внутри DO", f"BEGIN;\nDO $$ BEGIN {DEL} FROM listing_data.t; END $$;\nCOMMIT;\n"),
        (False, f"{DEL} во вложенном $q$ внутри функции",
         f"BEGIN;\nCREATE FUNCTION f() RETURNS void AS $f$ BEGIN EXECUTE $q$ {DEL} FROM t $q$; END $f$ LANGUAGE plpgsql;\nCOMMIT;\n"),
        # --- трюки разбора (замечание 4)
        (False, "комментарий -- с переводом строки в теле DO",
         f"BEGIN;\nDO $$ BEGIN -- x\n{DEL} FROM listing_data.t; END $$;\nCOMMIT;\n"),
        (False, "/**/ вплотную в теле DO", f"BEGIN;\nDO $$ BEGIN /**/{DEL} FROM listing_data.t; END $$;\nCOMMIT;\n"),
        (False, "имя \"a'b\" в теле DO",
         f"BEGIN;\nDO $$ DECLARE \"a'b\" int; BEGIN {DEL} FROM listing_data.t; END $$;\nCOMMIT;\n"),
        (False, "строка E'\\'' в теле DO",
         f"BEGIN;\nDO $$ BEGIN RAISE NOTICE E'\\''; {DEL} FROM listing_data.t; END $$;\nCOMMIT;\n"),
        (False, "строка E'\\'' снаружи", f"BEGIN;\nSELECT E'\\'';\n{DEL} FROM listing_data.t WHERE id = 1;\nCOMMIT;\n"),
        (False, "имя \"a'b\" снаружи",
         f"BEGIN;\nCREATE TABLE listing_data.\"a'b\" (id int);\n{DEL} FROM listing_data.t WHERE id = 1;\nCOMMIT;\n"),
        (False, "имя x$a$ — не начало тела $…$",
         f"BEGIN;\nCREATE TABLE listing_data.x$a$ (id int);\n{D} TABLE listing_data.t;\nCREATE TABLE y$a$ (id int);\nCOMMIT;\n"),
        # --- исключение для триггера (замечание 2)
        (False, f"{D} TRIGGER без пересоздания", f"BEGIN;\n{DROPTRG}COMMIT;\n"),
        (False, f"{D} TRIGGER без IF EXISTS", f"BEGIN;\n{D} TRIGGER tg ON listing_data.t;\n{TRG}COMMIT;\n"),
        (False, "пересоздание на другой таблице",
         f"BEGIN;\n{D} TRIGGER IF EXISTS tg ON listing_data.other;\n{TRG}COMMIT;\n"),
        (False, "CREATE TRIGGER только в строке",
         f"BEGIN;\n{DROPTRG}COMMENT ON TABLE listing_data.t IS 'CREATE TRIGGER tg BEFORE UPDATE ON listing_data.t ';\nCOMMIT;\n"),
        (False, "CREATE TRIGGER только в имени в кавычках",
         f"BEGIN;\n{DROPTRG}CREATE TABLE \"CREATE TRIGGER tg x ON listing_data.t \" (id int);\nCOMMIT;\n"),
        (False, "CREATE TRIGGER в комментарии", f"BEGIN;\n{DROPTRG}-- {TRG}COMMIT;\n"),
        (False, "CREATE TRIGGER после COMMIT", f"BEGIN;\n{DROPTRG}COMMIT;\n{TRG}"),
        (False, "CREATE раньше DROP — триггер остался бы удалён", f"BEGIN;\n{TRG}{DROPTRG}COMMIT;\n"),
        (False, "DROP после пересоздания — второй DROP без CREATE", f"BEGIN;\n{DROPTRG}{TRG}{DROPTRG}COMMIT;\n"),
        (True, "DROP, CREATE, DROP, CREATE — каждый DROP перед своим CREATE", f"BEGIN;\n{DROPTRG}{TRG}{DROPTRG}{TRG}COMMIT;\n"),
        (False, "имя триггера в кавычках", f"BEGIN;\n{D} TRIGGER IF EXISTS \"tg\" ON listing_data.t;\n"
                                           "CREATE TRIGGER \"tg\" BEFORE UPDATE ON listing_data.t FOR EACH ROW EXECUTE FUNCTION f();\nCOMMIT;\n"),
        # --- после COMMIT (замечание 1)
        (False, "после COMMIT — INSERT", "BEGIN;\nSELECT 1;\nCOMMIT;\nINSERT INTO listing_data.t VALUES (1);\n"),
        (False, "после COMMIT — UPDATE", "BEGIN;\nSELECT 1;\nCOMMIT;\nUPDATE listing_data.t SET id = 2;\n"),
        (False, "после COMMIT — SELECT … INTO", "BEGIN;\nSELECT 1;\nCOMMIT;\nSELECT * INTO listing_data.t2 FROM listing_data.t;\n"),
        (False, "после COMMIT — set_config", "BEGIN;\nSELECT 1;\nCOMMIT;\nSELECT set_config('a.b', 'c', false);\n"),
        (False, "после COMMIT — nextval", "BEGIN;\nSELECT 1;\nCOMMIT;\nSELECT nextval('listing_data.s');\n"),
        (False, "после COMMIT — SELECT … FOR UPDATE", "BEGIN;\nSELECT 1;\nCOMMIT;\nSELECT * FROM listing_data.t FOR UPDATE;\n"),
        (False, "после COMMIT — WITH, не SELECT", "BEGIN;\nSELECT 1;\nCOMMIT;\nWITH x AS (SELECT 1) SELECT 1;\n"),
        (False, "после COMMIT — DO", f"BEGIN;\nSELECT 1;\nCOMMIT;\nDO $$ BEGIN {DEL} FROM t; END $$;\n"),
        (False, f"после COMMIT — {D}", f"BEGIN;\nSELECT 1;\nCOMMIT;\n{D} TABLE listing_data.t;\n"),
    ]
    for i, (want_ok, name, sql) in enumerate(CASES):
        p = TMP / "migrations" / f"case_{i:02d}.sql"
        p.write_text(sql, encoding="utf-8")
        got = verdict(p, TMP)
        check(("пропускает: " if want_ok else "отказ: ") + name, got is want_ok)
finally:
    shutil.rmtree(TMP, ignore_errors=True)

check("настоящая migrations/ не тронута пробами", not list(MIG.glob("case_*.sql")) and not list(MIG.glob("zz_probe_*")))

# разбор проверочных запросов
q = am.statements("SELECT ';' AS a; -- комментарий; с точкой\nSELECT $$x;y$$ AS b; /* ; */ SELECT 'it''s' AS c;")
check(f"проверочные запросы режутся вне строк, $$ и комментариев ({len(q)})",
      q == ["SELECT ';' AS a", "SELECT $$x;y$$ AS b", "SELECT 'it''s' AS c"])
q = am.statements("SELECT E'a\\';b' AS d; SELECT \"x;y\" FROM t; SELECT $t$ $$; $t$ AS e;")
check(f"E'…', имена в кавычках и тег $t$ ({len(q)})",
      q == ["SELECT E'a\\';b' AS d", "SELECT \"x;y\" FROM t", "SELECT $t$ $$; $t$ AS e"])
src = (ROOT / "scratchpad" / "apply_migration.py").read_text(encoding="utf-8")
check("в коде проверочные запросы идут в сессии только на чтение", "conn.set_session(readonly=True)" in src)
check("учётка CLI сверяется с учёткой владельца", 'if me != OWNER:' in src)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
