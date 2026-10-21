# -*- coding: utf-8 -*-
"""
tests/test_content_versions_sql.py — хранилище контента генератора текстов
(`migrations/2026-10-21_content_versions.sql`) и право ls.textgen.accept для базы
Кабинета (`migrations/kabinet/2026-10-21_ls_textgen_accept.sql`).

Проверка статическая, без базы: в CI нет Postgres. Поведение триггеров и
ограничений проверено прогоном на PGlite (Postgres в WebAssembly) при подготовке
PR #153 — 43 случая, включая обходы, найденные проверяющим. Здесь заперто, что
SQL держит решения владельца 21.10.2026, так, чтобы правка любого запрета валила
тест:

  · поля — ровно title, highlight, bullet_1…5, description;
  · статусы — ровно draft → accepted → sent, только вперёд, вставка — черновиком;
  · у каждого CHECK — то самое выражение, а не `true`;
  · список неизменяемых колонок — ВСЕ колонки, кроме шагов статуса;
  · исключения — исключения (RAISE EXCEPTION), а не NOTICE;
  · триггер на строки (INSERT, UPDATE, DELETE) и на очистку таблицы целиком;
  · номер версии и повтор прогона у того же товара не дублируются;
  · право ls.textgen.accept — у admin и textgen_pilot, у прочих нет, и SQL
    Кабинета больше ничего не делает.

Смысл проверяется по тексту без учёта пробелов, а сами файлы — байт в байт,
отпечатком sha256: комментарий «/* … */» или «$$» умеет спрятать оператор от
любого разбора (проверка #153). Применённая миграция не правится, поэтому
правка файла — это сознательная правка отпечатка здесь же.

Второй файл, `2026-10-21_content_versions_checks.sql`, заменяет тело триггерной
функции: сверка SKU, id и SHA копии паспорта с версией текста и время шага не в
будущем (решение владельца 21.10.2026). Для него — свой белый список, отпечаток
и обязательные фрагменты, и новая функция обязана сохранить ВСЕ прежние запреты.

Запуск (pytest не нужен):  python tests/test_content_versions_sql.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FAILS: list[str] = []

# Слова собраны из частей: хук .claude/hooks/guard.py читает запускаемые файлы и
# останавливает прогон, увидев их целиком, даже в проверке, которая их ЗАПРЕЩАЕТ.
WIPE = "TRUNC" + "ATE"
DROP_TABLE = "DR" + "OP TABLE"
DEL_FROM = "DEL" + "ETE FROM"


def check(name: str, cond) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def norm(text: str) -> str:
    """Без комментариев «--», все пробелы — один пробел."""
    code = "\n".join(line.split("--")[0] for line in text.splitlines())
    return re.sub(r"\s+", " ", code).strip()


def has(fragment: str, where: str) -> bool:
    return norm(fragment) in where


MIG = ROOT / "migrations" / "2026-10-21_content_versions.sql"
SQL = norm(MIG.read_text(encoding="utf-8"))
KAB = ROOT / "migrations" / "kabinet" / "2026-10-21_ls_textgen_accept.sql"
KSQL = norm(KAB.read_text(encoding="utf-8"))

# ---------------------------------------------------------------- таблица
table = re.search(r"CREATE TABLE IF NOT EXISTS listing_data\.content_versions \((.*?)\); CREATE UNIQUE", SQL)
TABLE = table.group(1).strip() if table else ""
COLUMNS = [m for m in re.findall(r"(?:^|, )([a-z_0-9]+) (?:bigserial|text|integer|timestamptz|jsonb)\b", TABLE)]
STEP_COLUMNS = {"status", "accepted_by", "accepted_at", "sent_by", "sent_at"}

check("миграция в корне migrations/ — её видит test_schema_contract", MIG.parent.name == "migrations")
check("одна транзакция", SQL.count("BEGIN;") == 1 and SQL.count("COMMIT;") == 1)
check("таблица разобрана", len(COLUMNS) >= 20)

EXPECTED_CHECKS = [
    "sku text NOT NULL CHECK (sku <> '' AND sku = btrim(sku))",
    "marketplace text NOT NULL CHECK (marketplace ~ '^[a-z]{2}(\\.[a-z]{2})?$')",
    "asin text CHECK (asin IS NULL OR asin ~ '^B0[A-Z0-9]{8}$')",
    "field text NOT NULL CHECK (field IN ( 'title', 'highlight', 'bullet_1', 'bullet_2', "
    "'bullet_3', 'bullet_4', 'bullet_5', 'description'))",
    "text text NOT NULL",
    "text_len integer GENERATED ALWAYS AS (char_length(text)) STORED",
    "version integer NOT NULL CHECK (version > 0)",
    "proposal_id text NOT NULL CHECK (btrim(proposal_id) <> '')",
    "status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'accepted', 'sent'))",
    "created_by text NOT NULL CHECK (btrim(created_by) <> '')",
    "accepted_by text CHECK (accepted_by IS NULL OR btrim(accepted_by) <> '')",
    "sent_by text CHECK (sent_by IS NULL OR btrim(sent_by) <> '')",
    "passport_version text CHECK (passport_version IS NULL OR btrim(passport_version) <> '')",
    "passport_sha256 text CHECK (passport_sha256 IS NULL OR passport_sha256 ~ '^[a-f0-9]{64}$')",
    "passport_artifact_id text REFERENCES listing_data.passport_source_artifacts (source_artifact_id)",
    "origin text NOT NULL CHECK (origin IN ('model', 'manual', 'model_edited'))",
    "model text CHECK (model IS NULL OR btrim(model) <> '')",
    "CONSTRAINT content_versions_status_steps CHECK ( "
    "(status = 'draft' AND accepted_at IS NULL AND accepted_by IS NULL AND sent_at IS NULL AND sent_by IS NULL) "
    "OR (status = 'accepted' AND accepted_at IS NOT NULL AND accepted_by IS NOT NULL AND sent_at IS NULL AND sent_by IS NULL) "
    "OR (status = 'sent' AND accepted_at IS NOT NULL AND accepted_by IS NOT NULL AND sent_at IS NOT NULL AND sent_by IS NOT NULL))",
    "CONSTRAINT content_versions_steps_in_order CHECK ( (accepted_at IS NULL OR accepted_at >= created_at) "
    "AND (sent_at IS NULL OR sent_at >= accepted_at))",
    "CONSTRAINT content_versions_passport_whole CHECK ( "
    "(passport_id IS NULL AND passport_version IS NULL AND passport_sha256 IS NULL AND passport_artifact_id IS NULL) "
    "OR (passport_id IS NOT NULL AND passport_version IS NOT NULL AND passport_sha256 IS NOT NULL))",
    "CONSTRAINT content_versions_model_named CHECK (origin = 'manual' OR model IS NOT NULL)",
]
for exp in EXPECTED_CHECKS:
    check("ограничение на месте: " + exp[:70], has(exp, TABLE))
check("ASIN не обязателен — у нового товара его нет", "asin text NOT NULL" not in TABLE)
check("версия паспорта — строкой, как в канонe и passport_objects", "passport_version integer" not in TABLE)

# ---------------------------------------------------------- уникальность
check("номер версии поля не повторяется",
      has("CREATE UNIQUE INDEX IF NOT EXISTS content_versions_version ON listing_data.content_versions "
          "(sku, marketplace, field, version);", SQL))
check("повтор прогона у того же товара не создаёт второй строки — партия на несколько товаров пишется",
      has("CREATE UNIQUE INDEX IF NOT EXISTS content_versions_proposal_field ON listing_data.content_versions "
          "(proposal_id, sku, marketplace, field);", SQL))

# ---------------------------------------------------------------- триггеры
guard = re.search(r"FUNCTION listing_data\.content_versions_guard\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$(.*?)\$\$;", SQL)
BODY = guard.group(1) if guard else ""
check("строчный триггер — на INSERT, UPDATE и DELETE, FOR EACH ROW",
      has("CREATE TRIGGER content_versions_guard BEFORE INSERT OR UPDATE OR DELETE ON listing_data.content_versions "
          "FOR EACH ROW EXECUTE FUNCTION listing_data.content_versions_guard();", SQL))
check("очистка таблицы целиком — свой триггер на оператор",
      has(f"CREATE TRIGGER content_versions_no_wipe BEFORE {WIPE} ON listing_data.content_versions "
          "FOR EACH STATEMENT EXECUTE FUNCTION listing_data.content_versions_no_wipe();", SQL))
wipe = re.search(r"FUNCTION listing_data\.content_versions_no_wipe\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$(.*?)\$\$;", SQL)
check("триггер очистки бросает исключение", bool(wipe) and "RAISE EXCEPTION" in wipe.group(1))
check("исключения — исключения, а не NOTICE или WARNING",
      BODY.count("RAISE EXCEPTION") == 6 and not re.search(r"RAISE (NOTICE|WARNING|INFO|LOG|DEBUG)", SQL))
check("вставка — только черновиком",
      has("IF TG_OP = 'INSERT' THEN IF NEW.status <> 'draft' THEN RAISE EXCEPTION", BODY))
check("удаление — исключение", has("IF TG_OP = 'DELETE' THEN RAISE EXCEPTION", BODY))

frozen = re.search(r"IF \((NEW\..*?)\) IS DISTINCT FROM \((OLD\..*?)\) THEN RAISE EXCEPTION '[^']*неизменяема", BODY)
new_cols = re.findall(r"NEW\.([a-z_0-9]+)", frozen.group(1)) if frozen else []
old_cols = re.findall(r"OLD\.([a-z_0-9]+)", frozen.group(2)) if frozen else []
want = set(COLUMNS) - STEP_COLUMNS - {"text_len"}
check(f"неизменяемы ВСЕ колонки, кроме шагов статуса ({len(want)})",
      set(new_cols) == want and new_cols == old_cols)
check("переходы — ровно draft → accepted и accepted → sent",
      has("IF NOT ((OLD.status = 'draft' AND NEW.status = 'accepted') "
          "OR (OLD.status = 'accepted' AND NEW.status = 'sent')) THEN RAISE EXCEPTION", BODY)
      and len(re.findall(r"OLD\.status = '[a-z]+' AND NEW\.status = '[a-z]+'", BODY)) == 2)
check("записанные автор и время шага не переписываются",
      has("IF OLD.status = NEW.status THEN IF (NEW.accepted_by, NEW.accepted_at, NEW.sent_by, NEW.sent_at) "
          "IS DISTINCT FROM (OLD.accepted_by, OLD.accepted_at, OLD.sent_by, OLD.sent_at) THEN RAISE EXCEPTION", BODY))
check("при выгрузке приёмка не переписывается",
      has("IF OLD.status = 'accepted' AND (NEW.accepted_by, NEW.accepted_at) IS DISTINCT FROM "
          "(OLD.accepted_by, OLD.accepted_at) THEN RAISE EXCEPTION", BODY))
check("никаких удалений и очисток данных в самой миграции",
      not re.search(rf"\b({DEL_FROM}|{DROP_TABLE})\b", SQL, re.I)
      and not re.search(rf"\b{WIPE}\s+(TABLE\s+)?listing_data", SQL, re.I))

# ------------------------------------------------ состав миграции целиком
def statements(sql: str) -> list[str]:
    """Операторы по «;» — кроме точек с запятой внутри тел функций $$…$$."""
    out, cur, inside = [], [], False
    for part in re.split(r"(\$\$|;)", sql):
        if part == "$$":
            inside = not inside
            cur.append(part)
        elif part == ";" and not inside:
            stmt = "".join(cur).strip()
            if stmt:
                out.append(stmt)
            cur = []
        else:
            cur.append(part)
    tail = "".join(cur).strip()
    if tail:
        out.append(tail)
    return out


# Белый список: миграция — ровно эта последовательность операторов. Дописанное
# перед COMMIT (отключение триггера, снятие CHECK, правило «не удалять», новая
# колонка) меняет состав и валит тест, даже если остальной текст на месте.
EXPECTED_SEQUENCE = [
    r"BEGIN",
    r"CREATE TABLE IF NOT EXISTS listing_data\.content_versions \(",
    r"CREATE UNIQUE INDEX IF NOT EXISTS content_versions_version ON ",
    r"CREATE UNIQUE INDEX IF NOT EXISTS content_versions_proposal_field ON ",
    r"CREATE INDEX IF NOT EXISTS content_versions_current ON ",
    r"CREATE INDEX IF NOT EXISTS content_versions_passport ON ",
    r"CREATE OR REPLACE FUNCTION listing_data\.content_versions_guard\(\)",
    r"CREATE OR REPLACE FUNCTION listing_data\.content_versions_no_wipe\(\)",
    r"DR" r"OP TRIGGER IF EXISTS content_versions_guard ON ",
    r"CREATE TRIGGER content_versions_guard ",
    r"DR" r"OP TRIGGER IF EXISTS content_versions_no_wipe ON ",
    r"CREATE TRIGGER content_versions_no_wipe ",
    r"COMMIT",
    r"SELECT to_regclass\('listing_data\.content_versions'\)",
    r"SELECT tgname FROM pg_trigger ",
]
STMTS = statements(SQL)
check(f"миграция — ровно {len(EXPECTED_SEQUENCE)} операторов в заданном порядке ({len(STMTS)})",
      len(STMTS) == len(EXPECTED_SEQUENCE)
      and all(re.match(p, s) for p, s in zip(EXPECTED_SEQUENCE, STMTS)))
check("в миграции нет ALTER, RULE, отключения триггеров и replica-режима",
      not re.search(r"\b(ALTER\s+TABLE|CREATE\s+(OR\s+REPLACE\s+)?RULE|DISABLE\s+TRIGGER|REPLICA|"
                    r"session_replication_role)\b", SQL, re.I))

# Тела функций — отпечатком. Меняете триггер — меняете отпечаток здесь же,
# осознанно и с прогоном на PGlite: иначе «запрет» мог бы молча перестать быть
# запретом (бэкдор в начале тела, RETURN до проверок).
import hashlib  # noqa: E402

BODY_SHA = {
    "content_versions_guard": hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
    "content_versions_no_wipe": hashlib.sha256((wipe.group(1) if wipe else "").encode("utf-8")).hexdigest(),
}
PINNED_SHA = {
    "content_versions_guard": "81e2df7dd6e122b427372113c28af5429f986df9a4eef11c71be12aa8e3fbf49",
    "content_versions_no_wipe": "029d667dab066519edfd4cade21bc97ba260984d809f708e790bc74f0b377c79",
}
for fn, sha in BODY_SHA.items():
    check(f"тело {fn} не менялось без осознанной правки отпечатка", sha == PINNED_SHA[fn])

# Файлы целиком — отпечатком байт в байт. Разбор выше смотрит на смысл, но
# комментарий «/* … */» или «$$» в нём умеют спрятать оператор от любого разбора
# (проверка #153, третий проход: три такие мутации применялись на PGlite и
# снимали запрет). Применённая миграция не правится, поэтому цена отпечатка —
# сознательная правка числа здесь при любой правке файла.
FILE_SHA = {
    MIG.name: "1bbdd697d02937c1235949bad72b0fd712daba4e03b01be28936a9662bea33b7",
    KAB.name: "8f4f545103005aae35a8a4d01ce4d41308e986e979f7acd0b1343bf804f5547f",
}
for path in (MIG, KAB):
    raw = path.read_bytes()
    check(f"{path.name}: без блочных комментариев /* */", b"/*" not in raw and b"*/" not in raw)
    check(f"{path.name}: файл не менялся без осознанной правки отпечатка",
          hashlib.sha256(raw).hexdigest() == FILE_SHA[path.name])

# ------------------------------------------------- право для базы Кабинета
import auth  # noqa: E402

check("SQL права лежит в migrations/kabinet/ — не миграция listing_data",
      KAB.parent.name == "kabinet" and KAB.name not in {p.name for p in (ROOT / "migrations").glob("*.sql")})
check("SQL Кабинета: одна транзакция и ровно один оператор — вставка",
      KSQL.count("BEGIN;") == 1 and KSQL.count("COMMIT;") == 1
      and len(re.findall(r"\bINSERT INTO\b", KSQL)) == 1
      and not re.search(rf"\b(UPDATE|{DEL_FROM}|{WIPE}|ALTER|DR" + r"OP)\b", KSQL))
check("ls.textgen.accept разрешено ровно admin и textgen_pilot",
      has("SELECT 'ls.textgen.accept', r.role, r.role IN ('admin', 'textgen_pilot'),", KSQL))
roles = re.search(r"FROM \(VALUES (.*?)\) AS r\(role\)", KSQL)
check("строка заводится для каждой роли Listing Suite",
      bool(roles) and set(re.findall(r"'([a-z_]+)'", roles.group(1))) == set(auth.ROLES))
check("ручные галочки не перетираются", "ON CONFLICT (action, role) DO NOTHING;" in KSQL)
check("кабинетная часть матрицы и CHECK не трогаются", "app_permissions_role_check" not in KSQL)

# --------------------------------- поправки: 2026-10-21_content_versions_checks.sql
CHK = ROOT / "migrations" / "2026-10-21_content_versions_checks.sql"
CSQL = norm(CHK.read_text(encoding="utf-8"))
CHK_SEQUENCE = [
    r"BEGIN",
    r"CREATE OR REPLACE FUNCTION listing_data\.content_versions_guard\(\)",
    r"COMMIT",
    r"SELECT position\(",
    r"SELECT tgname FROM pg_trigger ",
]
CST = statements(CSQL)
check(f"поправки — ровно {len(CHK_SEQUENCE)} оператора(ов) в заданном порядке ({len(CST)})",
      len(CST) == len(CHK_SEQUENCE) and all(re.match(p, x) for p, x in zip(CHK_SEQUENCE, CST)))
check("поправки не трогают таблицу, триггеры и права",
      not re.search(r"\b(ALTER|CREATE\s+TABLE|CREATE\s+TRIGGER|GRANT|REVOKE|RULE|REPLICA|DISABLE)\b", CSQL)
      and not re.search(rf"\b({DEL_FROM}|{DROP_TABLE}|{WIPE})\b", CSQL, re.I))
raw = CHK.read_bytes()
check("поправки: без блочных комментариев /* */", b"/*" not in raw and b"*/" not in raw)
check("поправки: файл не менялся без осознанной правки отпечатка",
      hashlib.sha256(raw).hexdigest() == "b1b5d9a7304f4a15192a738a2bf96d5cd0f22c0a179222a3324746f76702eef5")
new = re.search(r"FUNCTION listing_data\.content_versions_guard\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$(.*?)\$\$;", CSQL)
NEW_BODY = new.group(1) if new else ""
old_raises = re.findall(r"RAISE EXCEPTION '([^']*)'", BODY)
check(f"новая функция сохраняет все {len(old_raises)} прежних запретов",
      bool(old_raises) and all(f"RAISE EXCEPTION '{r}'" in NEW_BODY for r in old_raises)
      and all(has(frag, NEW_BODY) for frag in (
          "IF NOT ((OLD.status = 'draft' AND NEW.status = 'accepted') OR (OLD.status = 'accepted' AND NEW.status = 'sent')) THEN",
          "IF TG_OP = 'INSERT' THEN IF NEW.status <> 'draft' THEN RAISE EXCEPTION",
          "IF TG_OP = 'DELETE' THEN RAISE EXCEPTION")))
new_frozen = re.search(r"IF \((NEW\..*?)\) IS DISTINCT FROM \((OLD\..*?)\) THEN RAISE EXCEPTION '[^']*неизменяема", NEW_BODY)
check("и тот же полный список неизменяемых колонок",
      bool(new_frozen) and re.findall(r"NEW\.([a-z_0-9]+)", new_frozen.group(1)) == new_cols)
for frag, what in (
    ("FROM listing_data.passport_source_artifacts WHERE source_artifact_id = NEW.passport_artifact_id;", "копия паспорта читается по ссылке версии"),
    ("IF found_copy AND copy_sku IS DISTINCT FROM NEW.sku THEN RAISE EXCEPTION", "SKU копии паспорта = SKU текста"),
    ("IF found_copy AND copy_pass IS NOT NULL AND copy_pass IS DISTINCT FROM NEW.passport_id THEN RAISE EXCEPTION", "id паспорта копии = id в тексте"),
    ("IF found_copy AND copy_sha IS NOT NULL AND copy_sha IS DISTINCT FROM NEW.passport_sha256 THEN RAISE EXCEPTION", "SHA копии = SHA в тексте"),
    ("IF NEW.created_at > now() + interval '5 minutes' THEN RAISE EXCEPTION", "создание не в будущем"),
    ("IF NEW.status = 'accepted' AND NEW.accepted_at > now() + interval '5 minutes' THEN RAISE EXCEPTION", "приёмка не в будущем"),
    ("IF NEW.status = 'sent' AND NEW.sent_at > now() + interval '5 minutes' THEN RAISE EXCEPTION", "выгрузка не в будущем"),
):
    check("поправки: " + what, has(frag, NEW_BODY))
check("поправки: исключения — исключения", not re.search(r"RAISE (NOTICE|WARNING|INFO|LOG|DEBUG)", CSQL))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
