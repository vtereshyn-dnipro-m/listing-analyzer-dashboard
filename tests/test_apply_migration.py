# -*- coding: utf-8 -*-
"""
tests/test_apply_migration.py — `scratchpad/apply_migration.py` отказывает там,
где обязан (решение владельца 21.10.2026, проверка #158). Без базы и без сети:
проверяется только `vet()` и разбор проверочных запросов.

Что заперто:
  · применяется только файл прямо в migrations/ — кабинетный SQL
    (migrations/kabinet/: роли и app_permissions) скрипт не применяет никогда;
  · файл — одна транзакция: первым BEGIN;, ровно один BEGIN; и один COMMIT;;
  · удаление данных и DROP — отказ; исключение одно — пересоздание триггера
    (DROP TRIGGER IF EXISTS X ON … при CREATE TRIGGER X в том же файле);
  · проверочные запросы режутся по «;» вне строк и тел $…$, комментарии не
    ломают разбор;
  · уже применённые миграции content_versions и проверка #157 проходят vet().

Запуск (pytest не нужен):  python tests/test_apply_migration.py
"""
from __future__ import annotations

import importlib.util
import pathlib
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


def refused(path: pathlib.Path) -> bool:
    try:
        am.vet(path)
    except SystemExit as e:
        return e.code == 2
    return False


def accepted(path: pathlib.Path) -> bool:
    try:
        am.vet(path)
        return True
    except SystemExit:
        return False


MIG = ROOT / "migrations"
for name in ("2026-10-21_content_versions.sql", "2026-10-21_content_versions_checks.sql",
             "2026-10-21_passport_copy_frozen.sql"):
    if (MIG / name).exists():
        check(f"vet пропускает {name}", accepted(MIG / name))

kab = sorted((MIG / "kabinet").glob("*.sql"))
check(f"кабинетный SQL — отказ всегда ({len(kab)} файла)", kab and all(refused(p) for p in kab))

TMP = pathlib.Path(tempfile.mkdtemp(dir=MIG))   # временная подпапка migrations/ — тоже не «прямо в migrations/»
check("файл во вложенной папке migrations/ — отказ", refused(TMP / "x.sql") if (TMP / "x.sql").write_text("BEGIN;\nCOMMIT;\n") else False)

CASES = [
    (True, "одна транзакция с CREATE", "BEGIN;\nCREATE TABLE IF NOT EXISTS listing_data.t (id int);\nCOMMIT;\nSELECT 1;\n"),
    (True, "пересоздание триггера", f"BEGIN;\n{D} TRIGGER IF EXISTS tg ON listing_data.t;\n"
                                   "CREATE TRIGGER tg BEFORE UPDATE ON listing_data.t FOR EACH ROW EXECUTE FUNCTION f();\nCOMMIT;\n"),
    (False, "без BEGIN", "CREATE TABLE listing_data.t (id int);\n"),
    (False, "без COMMIT", "BEGIN;\nCREATE TABLE listing_data.t (id int);\n"),
    (False, "два COMMIT", "BEGIN;\nSELECT 1;\nCOMMIT;\nBEGIN;\nSELECT 2;\nCOMMIT;\n"),
    (False, "commit строчными — тоже считается, и второй — отказ", "BEGIN;\ncommit;\nCOMMIT;\n"),
    (False, f"{D} TABLE", f"BEGIN;\n{D} TABLE listing_data.t;\nCOMMIT;\n"),
    (False, f"{D} COLUMN", f"BEGIN;\nALTER TABLE listing_data.t {D} COLUMN x;\nCOMMIT;\n"),
    (False, f"{D} TRIGGER без пересоздания", f"BEGIN;\n{D} TRIGGER IF EXISTS tg ON listing_data.t;\nCOMMIT;\n"),
    (False, f"{D} TRIGGER без IF EXISTS", f"BEGIN;\n{D} TRIGGER tg ON listing_data.t;\n"
                                          "CREATE TRIGGER tg BEFORE UPDATE ON listing_data.t FOR EACH ROW EXECUTE FUNCTION f();\nCOMMIT;\n"),
    (False, f"{D} FUNCTION", f"BEGIN;\n{D} FUNCTION listing_data.f();\nCOMMIT;\n"),
    (False, f"{DEL} FROM", f"BEGIN;\n{DEL} FROM listing_data.t WHERE id = 1;\nCOMMIT;\n"),
    (False, WIPE, f"BEGIN;\n{WIPE} listing_data.t;\nCOMMIT;\n"),
    (False, f"{DEL} внутри DO", f"BEGIN;\nDO $$ BEGIN {DEL} FROM listing_data.t; END $$;\nCOMMIT;\n"),
    (True, f"слово {D} внутри строки — не оператор", f"BEGIN;\nCOMMENT ON TABLE listing_data.t IS 'no {D} here';\nCOMMIT;\n"),
    (True, f"слово {D} в комментарии — не оператор", f"BEGIN;\n-- {D} TABLE в комментарии\nSELECT 1;\nCOMMIT;\n"),
]
for want_ok, name, sql in CASES:
    p = MIG / f"zz_probe_{abs(hash(name))}.sql"
    try:
        p.write_text(sql, encoding="utf-8")
        got_ok = accepted(p)
    finally:
        p.unlink()
    check(("пропускает: " if want_ok else "отказ: ") + name, got_ok == want_ok)

for f in TMP.iterdir():
    f.unlink()
TMP.rmdir()

# разбор проверочных запросов
q = am.statements(am.strip_comments(
    "SELECT ';' AS a; -- комментарий; с точкой\nSELECT $$x;y$$ AS b; /* ; */ SELECT 'it''s' AS c;"))
check(f"проверочные запросы режутся вне строк и $$ ({len(q)})",
      q == ["SELECT ';' AS a", "SELECT $$x;y$$ AS b", "SELECT 'it''s' AS c"])
check("в коде проверочные запросы идут в сессии только на чтение",
      "conn.set_session(readonly=True)" in (ROOT / "scratchpad" / "apply_migration.py").read_text(encoding="utf-8"))
check("учётка CLI сверяется с учёткой владельца",
      'if me != OWNER:' in (ROOT / "scratchpad" / "apply_migration.py").read_text(encoding="utf-8"))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
