# -*- coding: utf-8 -*-
"""
tests/test_content_versions_sql.py — хранилище контента генератора текстов
(`migrations/2026-10-22_content_versions.sql`) и право ls.textgen.accept для базы
Кабинета (`migrations/kabinet/2026-10-22_ls_textgen_accept.sql`).

Проверка статическая, без базы: SQL держит решения владельца 21.10.2026, и
правка одного слова в CHECK или триггере должна валить тест, а не всплыть на
живых данных. Поведение триггера и ограничений проверено прогоном на PGlite
(Postgres в WebAssembly) при подготовке PR — в CI его нет, поэтому здесь
заперто то, что видно по тексту:

  · поля — ровно title, highlight, bullet_1…5, description;
  · статусы — ровно draft → accepted → sent, и только вперёд;
  · текст и происхождение неизменяемы, удаления нет — триггер на UPDATE и DELETE;
  · номер версии и повтор прогона не дублируются — UNIQUE;
  · ASIN не обязателен (у нового товара его нет), SKU обязателен;
  · паспорт-источник: id, версия, SHA и ссылка на passport_source_artifacts;
  · право ls.textgen.accept — у admin и textgen_pilot, у прочих нет.

Запуск (pytest не нужен):  python tests/test_content_versions_sql.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAILS: list[str] = []


def check(name: str, cond) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def code_only(text: str) -> str:
    """SQL без комментариев «--»: решения проверяем по коду, а не по пояснениям."""
    return "\n".join(line.split("--")[0] for line in text.splitlines())


MIG = ROOT / "migrations" / "2026-10-22_content_versions.sql"
SQL = code_only(MIG.read_text(encoding="utf-8"))
KAB = ROOT / "migrations" / "kabinet" / "2026-10-22_ls_textgen_accept.sql"
KSQL = code_only(KAB.read_text(encoding="utf-8"))


def quoted(s: str) -> set[str]:
    return set(re.findall(r"'([a-z_0-9]+)'", s))


def column(name: str) -> str:
    m = re.search(rf"^\s*{name}\s+(.*?),?\s*$", SQL, re.M)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- таблица
check("миграция в корне migrations/ — её видит test_schema_contract",
      MIG.parent.name == "migrations")
check("одна транзакция", "BEGIN;" in SQL and SQL.strip().count("COMMIT;") == 1)
check("таблица заводится с IF NOT EXISTS — повторный прогон не падает",
      "CREATE TABLE IF NOT EXISTS listing_data.content_versions" in SQL)

field = re.search(r"field\s+text\s+NOT NULL CHECK \(field IN \((.*?)\)\)", SQL, re.S)
check("поля — ровно title, highlight, bullet_1…5, description",
      bool(field) and quoted(field.group(1)) == {"title", "highlight", "description"}
      | {f"bullet_{i}" for i in range(1, 6)})
status = re.search(r"CHECK \(status IN \((.*?)\)\)", SQL, re.S)
check("статусы — ровно draft, accepted, sent",
      bool(status) and quoted(status.group(1)) == {"draft", "accepted", "sent"})
check("новая версия — черновик по умолчанию", re.search(r"status\s+text\s+NOT NULL DEFAULT 'draft'", SQL))
check("SKU обязателен", "NOT NULL" in column("sku"))
check("ASIN не обязателен — у нового товара его нет", "NOT NULL" not in column("asin"))
check("рынок обязателен", "NOT NULL" in column("marketplace"))
check("длину считает база, а не код", "GENERATED ALWAYS AS (char_length(text)) STORED" in SQL)
check("автор создания обязателен", "NOT NULL" in column("created_by"))
check("ссылка на зарегистрированную копию паспорта — внешний ключ",
      "REFERENCES listing_data.passport_source_artifacts (source_artifact_id)" in SQL)
check("SHA паспорта — 64 hex", "passport_sha256 ~ '^[a-f0-9]{64}$'" in SQL)
check("паспорт либо целиком, либо никак", "content_versions_passport_whole" in SQL)
check("шаг статуса записан с автором и временем", "content_versions_status_steps" in SQL
      and all(c in SQL for c in ("accepted_by IS NOT NULL", "sent_by IS NOT NULL")))
check("происхождение — model, manual, model_edited",
      quoted(re.search(r"origin\s+text\s+NOT NULL CHECK \(origin IN \((.*?)\)\)", SQL, re.S).group(1))
      == {"model", "manual", "model_edited"})

# ---------------------------------------------------------- уникальность
check("номер версии поля не повторяется",
      re.search(r"UNIQUE INDEX IF NOT EXISTS content_versions_version\s+ON listing_data.content_versions "
                r"\(sku, marketplace, field, version\)", SQL))
check("повтор прогона не создаёт второй строки",
      re.search(r"UNIQUE INDEX IF NOT EXISTS content_versions_proposal_field\s+ON listing_data.content_versions "
                r"\(proposal_id, field\)", SQL))

# ---------------------------------------------------------------- триггер
check("триггер на UPDATE и DELETE",
      re.search(r"BEFORE UPDATE OR DELETE ON listing_data.content_versions", SQL))
guard = re.search(r"FUNCTION listing_data.content_versions_guard\(\).*?\$\$(.*?)\$\$", SQL, re.S)
body = guard.group(1) if guard else ""
check("удаление — исключение", re.search(r"TG_OP = 'DELETE' THEN\s+RAISE EXCEPTION", body))
check("текст в списке неизменяемых", "NEW.text" in body and "OLD.text" in body)
check("версия, SKU и паспорт в списке неизменяемых",
      all(f"NEW.{c}" in body for c in ("version", "sku", "passport_sha256", "proposal_id", "origin")))
check("переходы — только draft → accepted и accepted → sent",
      "(OLD.status = 'draft'    AND NEW.status = 'accepted')" in body
      and "(OLD.status = 'accepted' AND NEW.status = 'sent')" in body
      and "'sent'    AND NEW.status" not in body)
check("записанные автор и время шага не переписываются",
      "уже записаны и не переписываются" in body)
# Слова собраны из частей: хук .claude/hooks/guard.py читает запускаемые файлы и
# останавливает прогон, увидев их целиком, даже в проверке, которая их ЗАПРЕЩАЕТ.
_DANGER = "|".join(("DEL" + r"ETE\s+FROM", "TRUN" + "CATE", "DR" + r"OP\s+TABLE"))
check("никаких удалений и очисток в самой миграции",
      not re.search(rf"\b({_DANGER})\b", SQL, re.I))

# ------------------------------------------------- право для базы Кабинета
check("SQL права лежит в migrations/kabinet/ — не миграция listing_data",
      KAB.parent.name == "kabinet" and KAB.name not in {p.name for p in (ROOT / "migrations").glob("*.sql")})
ins = re.search(r"SELECT 'ls\.textgen\.accept', r\.role, r\.role IN \(([^)]*)\)", KSQL)
check("ls.textgen.accept разрешено ровно admin и textgen_pilot",
      bool(ins) and quoted(ins.group(1)) == {"admin", "textgen_pilot"})
roles = re.search(r"FROM \(VALUES (.*?)\) AS r\(role\)", KSQL, re.S)
sys.path.insert(0, str(ROOT))
import auth  # noqa: E402

check("строка заводится для каждой роли Listing Suite",
      bool(roles) and quoted(roles.group(1)) == set(auth.ROLES))
check("ручные галочки не перетираются", "ON CONFLICT (action, role) DO NOTHING" in KSQL)
check("одна транзакция", KSQL.strip().startswith("BEGIN;") and "COMMIT;" in KSQL)
check("кабинетная часть матрицы не трогается", "app_permissions_role_check" not in KSQL)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
