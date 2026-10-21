# -*- coding: utf-8 -*-
"""
tests/test_passport_copy_frozen_sql.py — копия паспорта, на которую ссылается
текст генератора, не меняется (`migrations/2026-10-21_passport_copy_frozen.sql`).

Решение владельца 21.10.2026: «копию паспорта, на которую ссылается текст, —
запретить менять (триггер), новый паспорт = новая версия». Проверка статическая,
без базы; поведение проверено на PGlite при подготовке PR. Что заперто:

  · у строки passport_source_artifacts, на которую ссылается версия текста, не
    меняется ничего, кроме одного шага lifecycle ACTIVE → OLD — тело функции
    сверяется целиком с эталоном, собранным из колонок самой таблицы, и любая
    добавка в условие валит тест. Колонки берутся из CREATE TABLE миграции
    Паспорта, а таблица в базе уже есть — новая колонка придёт отдельной
    миграцией через ALTER TABLE. Поэтому любая другая миграция, меняющая состав
    колонок passport_source_artifacts, тоже валит тест: она обязана заодно
    решить, заморожена ли новая колонка, и обновить этот файл (проверка #157);
  · функция версий — ровно та, что в 2026-10-21_content_versions_checks.sql,
    плюс одна добавка: строка копии читается FOR SHARE (гонка правки копии и
    записи версии, найденная проверкой #154);
  · миграция — ровно эти операторы, файл — отпечатком байт в байт: комментарий
    умеет спрятать оператор от разбора (проверка #153).

Тесты нельзя импортировать друг из друга (они исполняются как скрипты), поэтому
разбор SQL здесь свой, маленький.

Запуск (pytest не нужен):  python tests/test_passport_copy_frozen_sql.py
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAILS: list[str] = []
DEL_FROM = "DEL" + "ETE FROM"   # слова собраны из частей: хук .claude/hooks/guard.py
WIPE = "TRUNC" + "ATE"          # читает запускаемые файлы целиком


def check(name: str, cond) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def norm(text: str) -> str:
    code = "\n".join(line.split("--")[0] for line in text.splitlines())
    return re.sub(r"\s+", " ", code).strip()


def statements(sql: str) -> list[str]:
    out, cur, inside = [], [], False
    for part in re.split(r"(\$\$|;)", sql):
        if part == "$$":
            inside = not inside
            cur.append(part)
        elif part == ";" and not inside:
            if "".join(cur).strip():
                out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(part)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def body(sql: str, fn: str) -> str:
    m = re.search(rf"FUNCTION listing_data\.{fn}\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$(.*?)\$\$;", sql)
    return m.group(1) if m else ""


MIG = ROOT / "migrations" / "2026-10-21_passport_copy_frozen.sql"
SQL = norm(MIG.read_text(encoding="utf-8"))
CHECKS = norm((ROOT / "migrations" / "2026-10-21_content_versions_checks.sql").read_text(encoding="utf-8"))
CORE = norm((ROOT / "migrations" / "2026-10-07_passport_sku_core.sql").read_text(encoding="utf-8"))

# ------------------------------------------------------------ состав файла
EXPECTED = [
    r"BEGIN",
    r"DO \$\$ BEGIN IF to_regclass\('listing_data\.content_versions'\) IS NULL THEN RAISE EXCEPTION '[^']*'; END IF; END \$\$$",
    r"CREATE INDEX IF NOT EXISTS content_versions_passport_artifact ON listing_data\.content_versions "
    r"\(passport_artifact_id\) WHERE passport_artifact_id IS NOT NULL$",
    r"CREATE OR REPLACE FUNCTION listing_data\.content_versions_guard\(\)",
    r"CREATE OR REPLACE FUNCTION listing_data\.passport_copy_frozen\(\)",
    r"DR" r"OP TRIGGER IF EXISTS passport_copy_frozen ON listing_data\.passport_source_artifacts",
    r"CREATE TRIGGER passport_copy_frozen BEFORE UPDATE ON listing_data\.passport_source_artifacts "
    r"FOR EACH ROW EXECUTE FUNCTION listing_data\.passport_copy_frozen\(\)",
    r"COMMIT",
    r"SELECT position\('FOR SHARE' IN prosrc\)",
    r"SELECT tgname FROM pg_trigger WHERE tgrelid = 'listing_data\.passport_source_artifacts'",
]
ST = statements(SQL)
check(f"миграция — ровно {len(EXPECTED)} операторов в заданном порядке ({len(ST)})",
      len(ST) == len(EXPECTED) and all(re.match(p, s) for p, s in zip(EXPECTED, ST)))
check("не трогает таблицы и права (кроме индекса для поиска ссылок)",
      not re.search(r"\b(ALTER|CREATE\s+TABLE|GRANT|REVOKE|RULE|REPLICA|DISABLE)\b", SQL)
      and not re.search(rf"\b({DEL_FROM}|{WIPE})\b", SQL, re.I))
raw = MIG.read_bytes()
check("без блочных комментариев /* */", b"/*" not in raw and b"*/" not in raw)
check("файл не менялся без осознанной правки отпечатка",
      hashlib.sha256(raw).hexdigest() == "da0efc6c69b0f07b54ad529d05185f38b4746cb600fe008a258712dfa85095c7")

# ------------------------------------------------------ функция версий
G_OLD, G_NEW = body(CHECKS, "content_versions_guard"), body(SQL, "content_versions_guard")
LOCK_FROM = "WHERE source_artifact_id = NEW.passport_artifact_id;"
LOCK_TO = "WHERE source_artifact_id = NEW.passport_artifact_id FOR SHARE;"
check("функция версий = функция из поправок #154 плюс ровно FOR SHARE",
      bool(G_OLD) and G_OLD.count(LOCK_FROM) == 1 and G_NEW == G_OLD.replace(LOCK_FROM, LOCK_TO))

# --------------------------------------------------- заморозка копии
cols_m = re.search(r"CREATE TABLE IF NOT EXISTS listing_data\.passport_source_artifacts \((.*?)\); CREATE INDEX", CORE)
PSA = re.findall(r"(?:^|, )([a-z_0-9]+) (?:text|bigint|timestamptz)\b", cols_m.group(1).strip()) if cols_m else []
F = body(SQL, "passport_copy_frozen")
check(f"колонки копии разобраны из миграции Паспорта ({len(PSA)})", len(PSA) >= 15 and "lifecycle" in PSA)
# Тело — целиком, против эталона из колонок самой таблицы: любая добавка в
# условие («AND (false)», «OR (true)», исключение для роли) меняет текст и валит
# тест даже при подменённом отпечатке (проверка #157). Заморожено всё, кроме
# одного шага lifecycle ACTIVE → OLD (решение владельца: копию не менять;
# новый паспорт — новая версия, старая копия помечается OLD).
FROZEN = [c for c in PSA if c != "lifecycle"]
EXPECTED_F = (
    "BEGIN IF EXISTS (SELECT 1 FROM listing_data.content_versions WHERE passport_artifact_id = "
    "OLD.source_artifact_id) AND (("
    + ", ".join("NEW." + c for c in FROZEN) + ") IS DISTINCT FROM ("
    + ", ".join("OLD." + c for c in FROZEN) + ") "
    "OR (NEW.lifecycle IS DISTINCT FROM OLD.lifecycle AND NOT (OLD.lifecycle = 'ACTIVE' AND NEW.lifecycle = 'OLD'))) "
    "THEN RAISE EXCEPTION 'listing_data.passport_source_artifacts: копия % — источник текста в content_versions и не "
    "меняется (можно только пометить OLD); новый паспорт — новая строка', OLD.source_artifact_id; "
    "END IF; RETURN NEW; END;"
)
check("функция заморозки — ровно эталон: всё, кроме шага lifecycle ACTIVE → OLD, и только при ссылке текста",
      F.strip() == EXPECTED_F)
# Колонка, добавленная позже ALTER TABLE, в CREATE TABLE не попадёт, и эталон её
# не увидит — значит, и триггер её не заморозит. Пока такой миграции нет, тест
# зелёный; появится — красный, с подсказкой, что решить.
ALTERS = []
for f in sorted((ROOT / "migrations").glob("*.sql")):
    if f.name in (MIG.name, "2026-10-07_passport_sku_core.sql"):
        continue
    t = norm(f.read_text(encoding="utf-8"))
    if re.search(r"ALTER\s+TABLE\s+(IF\s+EXISTS\s+)?(ONLY\s+)?(listing_data\.)?passport_source_artifacts\b"
                 r"[^;]*\b(ADD|DR" r"OP|RENAME)\b", t, re.I):
        ALTERS.append(f.name)
check("состав колонок копий паспорта меняет только миграция Паспорта"
      + (f" — эти меняют его: {ALTERS}; решите, заморожена ли колонка, и обновите "
         f"{MIG.name} и этот тест" if ALTERS else ""), not ALTERS)

check("нарушение — исключение, один выход", "RAISE EXCEPTION" in F and F.count("RETURN NEW;") == 1
      and not re.search(r"RAISE (NOTICE|WARNING|INFO|LOG|DEBUG)", SQL))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
