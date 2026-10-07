# -*- coding: utf-8 -*-
"""
tests/test_passport_vocab.py — словарь статусов в базе Паспорта взят из канона,
а не придуман.

Канон Паспорта SKU прямо запрещает добавлять статусы, вердикты и решения,
которых в нём нет (00A «Запрет произвольных изменений»). Таблицы
`migrations/2026-10-07_passport_sku_core.sql` держат статусы закрытым
словарём через CHECK, и этот тест сверяет КАЖДЫЙ такой словарь с текстом
канона из снимка: лишнее значение в базе — это статус, который канон не
знает; недостающее — статус канона, который база откажется сохранить.

Сверяется:
- состояния Паспорта — 00A «Допустимые состояния Паспорта»;
- статусы вопроса — 06E «Question: OPEN → SENT → …» плюс supersede и вывод
  из scope из ТЗ 11.5 (и только они);
- вердикты по ответу — 06E «Answer: RECEIVED → VERIFIED | PARTIAL | REJECTED»;
- решения по конфликту — ровно четыре из ТЗ 11.4.3;
- состояния запуска — объединение «Стани Run State» контракта графа и enum
  схемы run_state (они расходятся, см. canon/REFERENCE_DRIFT.md);
- terminal и execution_mode — enum схемы run_state;
- форматы ID вопроса и блокера — `Q-<RUN>-<NNN>`, `BLK-<RUN>-<NNN>` (ТЗ 3.1).

Запуск (pytest не нужен):  python tests/test_passport_vocab.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP = ROOT / "canon" / "ai_design_conveyor"
SQL = (ROOT / "migrations" / "2026-10-07_passport_sku_core.sql").read_text(encoding="utf-8")

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def sql_enum(table: str, column: str) -> set[str]:
    """Значения из `CHECK (column IN (...))` в CREATE TABLE этой таблицы:
    `status` есть и у Паспорта, и у вопроса — искать надо в своей таблице."""
    body = re.search(r"CREATE TABLE IF NOT EXISTS listing_data\." + table + r" \((.*?)\n\);", SQL, re.S)
    assert body, f"в миграции нет таблицы {table}"
    m = re.search(r"\b" + column + r"\s+IN\s*\(([^)]*)\)", body.group(1), re.S)
    assert m, f"в {table} нет CHECK для {column}"
    return set(re.findall(r"'([A-Z_]+)'", m.group(1)))


def chain(text: str, label: str) -> set[str]:
    """Статусы из строки 06E вида «- Question: `OPEN → SENT → …`»."""
    line = re.search(r"^- " + label + r": ([^\n]+)", text, re.M).group(1)
    return set(re.findall(r"\b[A-Z][A-Z_]{2,}\b", line))


def doc(rel: str) -> str:
    return (SNAP / rel).read_text(encoding="utf-8")


a00 = doc("02_SKU_Passport/00A_Контракт_передач_Паспорта_SKU.md")
states_00a = set(re.findall(r"`([A-Z_]+)`",
                            re.search(r"Допустимые состояния Паспорта:([^\n]+)", a00).group(1)))
check(f"состояния Паспорта = 00A {sorted(states_00a)}", sql_enum("passport_objects", "state") == states_00a)

q06e = doc("02_SKU_Passport/06E_MVP_Реестр_вопросов_и_ответов.md")
q_chain = chain(q06e, "Question")
q_sql = sql_enum("passport_questions", "status")
check(f"статусы вопроса содержат цепочку 06E {sorted(q_chain)}", len(q_chain) >= 4 and q_chain <= q_sql)
check(f"сверх 06E только supersede и вывод из scope (ТЗ 11.5): {sorted(q_sql - q_chain)}",
      q_sql - q_chain == {"SUPERSEDED", "OUT_OF_SCOPE"})

a_chain = chain(q06e, "Answer") & {"RECEIVED", "VERIFIED", "PARTIAL", "REJECTED"}
check(f"вердикты по ответу = 06E без RECEIVED {sorted(a_chain - {'RECEIVED'})}",
      len(a_chain) == 4 and sql_enum("passport_answer_verdicts", "verdict") == a_chain - {"RECEIVED"})

tz = doc("02_SKU_Passport/Listing_Suite_ТЗ_Контент_Паспорт_SKU.md")
decisions = {"KEEP_CURRENT", "ACCEPT_NEW", "KEEP_DISPUTED", "NOT_APPLICABLE"}
check("решения по конфликту — ровно четыре из ТЗ 11.4.3, и все четыре в тексте ТЗ",
      sql_enum("passport_answers", "decision") == decisions and all(f"`{d}`" in tz for d in decisions))

graph = doc("10_Runtime_Registry/AI_DESIGN_EXECUTION_GRAPH_CONTRACT.md")
section = graph.split("## Стани Run State")[1].split("\n## ")[0]
contract_states = set(re.findall(r"^- `([A-Z_]+)`", section, re.M))
schema = json.loads(doc("10_Runtime_Registry/ai_design_run_state.schema.json"))
schema_states = set(schema["properties"]["lifecycle_state"]["enum"])
check(f"состояния запуска = контракт ∪ схема ({len(contract_states | schema_states)})",
      sql_enum("passport_runs", "lifecycle_state") == contract_states | schema_states)
check("terminal_status = enum схемы run_state",
      sql_enum("passport_runs", "terminal_status") == set(schema["$defs"]["terminal"]["properties"]["status"]["enum"]))
modes = set(schema["properties"]["execution_mode"]["enum"])
check(f"execution_mode ⊆ схемы run_state и без GRAPH_SPEC_ONLY (это режим описания, не запуска)",
      sql_enum("passport_runs", "execution_mode") <= modes and "GRAPH_SPEC_ONLY" not in sql_enum("passport_runs", "execution_mode"))

check("формат ID вопроса Q-<RUN>-<NNN> есть в ТЗ и в CHECK",
      "Q-<RUN>-<NNN>" in tz and "'^Q-[A-Za-z0-9._-]+-[0-9]{3,}$'" in SQL)
check("формат блокера BLK-<RUN>-<NNN> есть в ТЗ и в CHECK",
      "BLK-<RUN>-<NNN>" in tz and "'^BLK-[A-Za-z0-9._-]+-[0-9]{3,}$'" in SQL)
check("один ACTIVE Паспорт на SKU держит база: частичный уникальный индекс",
      re.search(r"UNIQUE INDEX[^;]+\(sku_id\)\s+WHERE status = 'ACTIVE'", SQL) is not None)
for t in ("passport_run_events", "passport_receipts", "passport_answers", "passport_answer_verdicts"):
    check(f"{t} — только дописывание (триггер)", f"'{t}'" in SQL.split("FOREACH t IN ARRAY")[1])

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
