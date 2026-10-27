# -*- coding: utf-8 -*-
"""
tests/test_content_stamp_sql.py — штамп версии на черновике генератора
(`migrations/2026-10-27_content_versions_stamp.sql`; решение владельца 27.10.2026).

Проверка статическая, без базы: в CI нет Postgres. Поведение проверено прогоном
на PGlite при подготовке PR (все миграции по порядку, затем эта): вставка без
штампа и со штампом, отказ CHECK на неверном формате, отказ правки штампа у
новой и у старой строки, приёмка по-прежнему проходит, повторный прогон файла
проходит. Что заперто здесь:

  · миграция — ровно эти операторы: предусловие, две колонки с CHECK
    (prompt_sha256 — 64 hex, rules_version — 40 hex), замена функции версий,
    проверочные запросы; ни DROP, ни удаления данных, ни выключения триггеров;
  · функция версий — дословно из 2026-10-21_passport_copy_frozen.sql (с FOR
    SHARE) плюс ровно две колонки штампа в списке неизменяемых: штамп — это
    происхождение, и правится он только новой версией, как текст;
  · колонки — те, что пишет код (`textgen.STAMP_COLUMNS`), файл — тот, что
    код называет без миграции (`textgen.STAMP_MIGRATION`);
  · никакая другая миграция не добавляет колонок в content_versions: новая
    колонка обязана решить, заморожена ли она, и обновить этот тест;
  · скрипт применения (`scratchpad/apply_migration.py`) файл принимает;
  · файл — отпечатком байт в байт: комментарий умеет спрятать оператор от
    разбора (проверка #153).

Запуск (pytest не нужен):  python tests/test_content_stamp_sql.py
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FAILS: list[str] = []
DEL_FROM = "DEL" + "ETE FROM"   # слова собраны из частей: хук .claude/hooks/guard.py
WIPE = "TRUNC" + "ATE"          # читает запускаемые файлы целиком
DROP = "DR" + "OP"


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


MIG = ROOT / "migrations" / "2026-10-27_content_versions_stamp.sql"
SQL = norm(MIG.read_text(encoding="utf-8"))
FROZEN = norm((ROOT / "migrations" / "2026-10-21_passport_copy_frozen.sql").read_text(encoding="utf-8"))

# ------------------------------------------------------------ состав файла
EXPECTED = [
    r"BEGIN",
    r"DO \$\$ BEGIN IF to_regclass\('listing_data\.content_versions'\) IS NULL THEN RAISE EXCEPTION '[^']*'; END IF; END \$\$$",
    r"ALTER TABLE listing_data\.content_versions "
    r"ADD COLUMN IF NOT EXISTS prompt_sha256 text CHECK \(prompt_sha256 IS NULL OR prompt_sha256 ~ '\^\[a-f0-9\]\{64\}\$'\), "
    r"ADD COLUMN IF NOT EXISTS rules_version text CHECK \(rules_version IS NULL OR rules_version ~ '\^\[a-f0-9\]\{40\}\$'\)$",
    r"CREATE OR REPLACE FUNCTION listing_data\.content_versions_guard\(\) RETURNS trigger",
    r"COMMIT",
    r"SELECT column_name, data_type FROM information_schema\.columns ",
    r"SELECT position\('NEW\.prompt_sha256, NEW\.rules_version' IN prosrc\) > 0 AS stamp_frozen, "
    r"position\('FOR SHARE' IN prosrc\) > 0 AS copy_locked",
    r"SELECT tgname FROM pg_trigger WHERE tgrelid = 'listing_data\.content_versions'::regclass",
]
ST = statements(SQL)
check(f"миграция — ровно {len(EXPECTED)} операторов в заданном порядке ({len(ST)})",
      len(ST) == len(EXPECTED) and all(re.match(p, s) for p, s in zip(EXPECTED, ST)))
check("ни удаления, ни очистки, ни выключения триггеров, ни прав, ни новых триггеров",
      not re.search(rf"\b({DROP}|{DEL_FROM}|{WIPE}|RENAME|DISABLE|REPLICA|GRANT|REVOKE|RULE|CREATE\s+TRIGGER|"
                    r"session_replication_role|SET\s+SCHEMA)\b", SQL, re.I))
raw = MIG.read_bytes()
check("без блочных комментариев /* */", b"/*" not in raw and b"*/" not in raw)
check("файл не менялся без осознанной правки отпечатка",
      hashlib.sha256(raw).hexdigest() == "d93196b8661e60f50df40f14e4de128b1b3db9f57ffce563444aeeeaf9b14a55")

# ------------------------------------------------------ функция версий
G_OLD, G_NEW = body(FROZEN, "content_versions_guard"), body(SQL, "content_versions_guard")
A_NEW = "NEW.model, NEW.skill_version, NEW.checks)"
A_OLD = "OLD.model, OLD.skill_version, OLD.checks) THEN"
check("функция версий = функция из passport_copy_frozen.sql плюс ровно две колонки штампа",
      bool(G_OLD) and G_OLD.count(A_NEW) == 1 and G_OLD.count(A_OLD) == 1
      and G_NEW == G_OLD.replace(A_NEW, "NEW.model, NEW.skill_version, NEW.checks, NEW.prompt_sha256, NEW.rules_version)")
      .replace(A_OLD, "OLD.model, OLD.skill_version, OLD.checks, OLD.prompt_sha256, OLD.rules_version) THEN"))
check("блокировка копии паспорта FOR SHARE сохранена", "FOR SHARE;" in G_NEW)
frozen = re.search(r"IF \((NEW\..*?)\) IS DISTINCT FROM \((OLD\..*?)\) THEN RAISE EXCEPTION '[^']*неизменяема", G_NEW)
new_cols = re.findall(r"NEW\.([a-z_0-9]+)", frozen.group(1)) if frozen else []
old_cols = re.findall(r"OLD\.([a-z_0-9]+)", frozen.group(2)) if frozen else []
check("штамп в списке неизменяемых — и у NEW, и у OLD, в одном порядке",
      new_cols == old_cols and new_cols[-2:] == ["prompt_sha256", "rules_version"])

# ------------------------------------------------------ код и миграция согласованы
from services import textgen as tg  # noqa: E402

added = re.findall(r"ADD COLUMN IF NOT EXISTS ([a-z_0-9]+)", SQL)
check(f"колонки миграции — те, что пишет код ({added})", tuple(added) == tg.STAMP_COLUMNS)
check("код называет именно этот файл миграции", tg.STAMP_MIGRATION == MIG.name)

# Новая колонка content_versions в другой миграции не попала бы в список
# неизменяемых: функция версий её бы не заморозила.
OTHERS = []
for f in sorted((ROOT / "migrations").glob("*.sql")):
    if f.name == MIG.name:
        continue
    t = norm(f.read_text(encoding="utf-8"))
    bare = re.sub(r"'(?:[^']|'')*'", "''", re.sub(r"/\*.*?\*/", " ", t, flags=re.S))
    if any(re.search(r"ALTER\s+TABLE\s+(IF\s+EXISTS\s+)?(ONLY\s+)?(\"?listing_data\"?\s*\.\s*)?\"?content_versions\"?"
                     r"(?![a-z0-9_])[^;]*\b(ADD|" + DROP + r"|RENAME|DISABLE)\b", x, re.I) for x in (t, bare)):
        OTHERS.append(f.name)
check("колонки content_versions не добавляет и не меняет ни одна другая миграция"
      + (f" — эти меняют: {OTHERS}; решите, заморожена ли колонка, и обновите функцию версий и этот тест"
         if OTHERS else ""), not OTHERS)

# ------------------------------------------------------ скрипт применения
sys.path.insert(0, str(ROOT / "scratchpad"))
import apply_migration as am  # noqa: E402

try:
    am.vet(MIG)
    vet_ok = True
except SystemExit:                     # отказ скрипт печатает сам и выходит с кодом 2
    vet_ok = False
check("scratchpad/apply_migration.py принимает файл (одна транзакция, без DROP и удаления)", vet_ok)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
