# -*- coding: utf-8 -*-
"""
tests/test_schema_contract.py — код не читает несуществующих таблиц.

До сих пор схему проверить было нечем: DDL ноутбучных таблиц живёт
в Databricks, в репозитории его не было (пункт 4 аудита 29.08). Цена
известна поимённо: `policy_alerts` месяцами читалась страницей
«Методология», исключение уходило в общий `except`, и человек видел
«Новых изменений нет — все источники соответствуют текущим
методологиям». Утверждение о политиках Amazon, сделанное на пустом
месте, потому что таблицы нет вовсе.

Проверка идёт БЕЗ базы: имена таблиц достаются из SQL в коде и
сверяются со снимком схемы (`schema/objects.txt`) плюс таблицами,
которые создают миграции в репозитории. Второе слагаемое обязательно:
иначе свежая миграция роняла бы тест до обновления снимка, и первым
же действием тест бы отключили.

Известные расхождения перечислены в KNOWN_MISSING — и список
проверяется сам: объект, который в схеме ПОЯВИЛСЯ, обязан из него
уйти. Список исключений, никем не сверяемый, через месяц становится
списком «всё нормально».

Запуск (pytest не нужен):  python tests/test_schema_contract.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# Таблицы, которых в базе нет, а код к ним обращается. Каждая — с
# объяснением, почему это пока допустимо.
KNOWN_MISSING = {
    "policy_alerts": "таблицы нет; страница объявляет «слежение не "
                     "ведётся» вместо «изменений нет», см. PR #63",
}

SQL_HINT = re.compile(r"\bSELECT\b|\bINSERT\s+INTO\b|\bUPDATE\b|\bDELETE\s+FROM\b",
                      re.I)
REF = re.compile(
    r"\b(?:FROM|JOIN|INSERT\s+INTO|UPDATE)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.I)
# CTE объявляется единственным способом — «имя AS (»; алиасы так не пишутся
CTE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\(", re.I)
# слова, которые синтаксически стоят на месте имени таблицы
NOT_A_TABLE = {"lateral", "select", "only", "set"}


def tables_in_code() -> dict[str, set[str]]:
    """Имена таблиц из SQL-литералов кода → в каких файлах встретились."""
    used: dict[str, set[str]] = {}
    for path in sorted(list((ROOT / "pages").glob("*.py"))
                       + list((ROOT / "services").glob("*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)):
                continue
            sql = node.value
            if not SQL_HINT.search(sql):
                continue
            local = {m.lower() for m in CTE.findall(sql)} | NOT_A_TABLE
            for name in REF.findall(sql):
                if name.lower() in local:
                    continue
                used.setdefault(name.lower(), set()).add(path.name)
    return used


def schema_objects() -> set[str]:
    """Снимок схемы: имя объекта → строка «<имя> <table|view>»."""
    out = set()
    for line in (ROOT / "schema/objects.txt").read_text(
            encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line.split()[0].lower())
    return out


def migration_tables() -> set[str]:
    """Таблицы, которые заводят миграции в репозитории."""
    pat = re.compile(
        r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+(?:listing_data\.)?"
        r"([a-zA-Z_][a-zA-Z0-9_]*)", re.I)
    out = set()
    for f in (ROOT / "migrations").glob("*.sql"):
        out |= {m.lower() for m in pat.findall(f.read_text(encoding="utf-8"))}
    return out


USED = tables_in_code()
KNOWN = schema_objects() | migration_tables()

check(f"из кода извлечены имена таблиц ({len(USED)})", len(USED) >= 20)
check("снимок схемы прочитан", len(schema_objects()) >= 25)
check("таблицы миграций попали в допустимые",
      "figma_products" in migration_tables())

# --- главное: каждая читаемая таблица существует
missing = {n: files for n, files in USED.items() if n not in KNOWN}
unexpected = {n: f for n, f in missing.items() if n not in KNOWN_MISSING}
check(f"код не читает несуществующих таблиц ({unexpected or 'нет'})",
      not unexpected)

# --- и наоборот: список исключений не должен переживать починку
stale = [n for n in KNOWN_MISSING if n in KNOWN]
check(f"список известных расхождений не устарел ({stale or 'чист'})",
      not stale)
check("известное расхождение действительно наблюдается в коде",
      all(n in USED for n in KNOWN_MISSING))

# --- ON CONFLICT работает только при уникальном ключе по ТЕМ ЖЕ колонкам
# Иначе Postgres отвечает «there is no unique or exclusion constraint
# matching the ON CONFLICT specification», и падает не тест, а человек
# за экраном. 08.09 это чуть не случилось: миграция сменила ключ
# figma_products, а save_parsed ссылался на снесённый.
CONFLICT = re.compile(
    r"INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)(.*?)ON\s+CONFLICT\s*\(([^)]*)\)",
    re.I | re.S)


def unique_keys() -> set[tuple[str, tuple[str, ...]]]:
    """Уникальные ключи: снимок базы плюс таблицы, которых в нём ещё нет.

    Миграции подмешиваются ТОЛЬКО для таблиц, отсутствующих в снимке.
    Иначе множество копит историю: миграция 07.09 объявила
    `figma_products UNIQUE (figma_file_key, figma_node_id)`, миграция
    08.09 этот ключ снесла — но объявление осталось в файле, и проверка
    считала бы снесённый ключ живым. Первая версия этой функции так
    и делала, и мутация прошла мимо неё.
    """
    keys = set()
    snapshot_tables = set()
    for line in (ROOT / "schema/unique_keys.txt").read_text(
            encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tbl, cols = line.split()
            keys.add((tbl.lower(), tuple(c.strip() for c in cols.split(","))))
            snapshot_tables.add(tbl.lower())
    mig = re.compile(r"UNIQUE\s*\(([^)]*)\)", re.I)
    tbl_pat = re.compile(
        r"(?:CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|ALTER\s+TABLE)\s+"
        r"(?:listing_data\.)?([a-zA-Z_][a-zA-Z0-9_]*)", re.I)
    for f in (ROOT / "migrations").glob("*.sql"):
        text = f.read_text(encoding="utf-8")
        for chunk in re.split(r";", text):
            names = [n.lower() for n in tbl_pat.findall(chunk)
                     if n.lower() not in snapshot_tables]
            for cols in mig.findall(chunk):
                for name in names:
                    keys.add((name,
                              tuple(c.strip() for c in cols.split(","))))
    return keys


KEYS = unique_keys()
bad_conflicts = []
for path in sorted(list((ROOT / "pages").glob("*.py"))
                   + list((ROOT / "services").glob("*.py"))):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        for table, _mid, cols in CONFLICT.findall(node.value):
            want = tuple(c.strip() for c in cols.split(","))
            if (table.lower(), want) not in KEYS:
                bad_conflicts.append(f"{path.name}: {table} {want}")

check(f"ON CONFLICT опирается на существующий ключ ({bad_conflicts or 'да'})",
      not bad_conflicts)
check("снимок ключей прочитан", len(KEYS) >= 30)

# --- разбор SQL сам по себе: CTE и алиасы таблицами не считаются
_probe = """
    WITH last_run AS (SELECT asin FROM diagnosis),
         prev_run AS (SELECT asin FROM diagnosis)
    SELECT * FROM last_run l JOIN prev_run p ON p.asin = l.asin
     LEFT JOIN LATERAL (SELECT 1) x ON TRUE
"""
_names = {m.lower() for m in REF.findall(_probe)} - NOT_A_TABLE
_ctes = {m.lower() for m in CTE.findall(_probe)}
check("CTE не принимается за таблицу", not (_names - _ctes - {"diagnosis"}))
check("LATERAL не принимается за таблицу", "lateral" not in _names - _ctes)

# --- снимок и реестр в CLAUDE.md не должны расходиться молча
_doc = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
_undocumented = sorted(n for n in USED
                       if n in KNOWN and f"`{n}`" not in _doc)
check(f"каждая читаемая таблица описана в CLAUDE.md ({_undocumented or 'все'})",
      not _undocumented)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
