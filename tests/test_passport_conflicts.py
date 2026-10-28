# -*- coding: utf-8 -*-
"""
tests/test_passport_conflicts.py — конфликты паспорта по статусу и решения
верификатора (решения владельца 28.10.2026). Без сети и базы.

Что заперто:
  · закрытым считается только статус, начинающийся с RESOLVED, CLOSED, DECIDED
    или SCOPED_APART; OPEN_*, пустой, незнакомый и опечатка — открытый и
    вырезается (ошибиться в сторону «не дать модели» дешевле);
  · закрытый в паспорте конфликт значений не вырезает;
  · решение верификатора: выбранная сторона или своё значение идёт в модель
    разделом «РЕШЕНИЯ», отвергнутая сторона по-прежнему вырезается; решение по
    конфликту, которого в копии нет, не применяется;
  · таблица «Конфлікти» читается по шапке, «Джерело рішення» — колонкой;
  · генерация берёт решения из базы ДО вызова модели, по копии и её SHA;
    решение по другой копии (v3, другой SHA) не действует;
  · сервис решений: без проверяемого источника, без своего значения и по
    чужому конфликту — отказ; запись — одна строка, без UPDATE и DELETE;
  · миграция таблицы решений: только дописывание (триггер на UPDATE, DELETE и
    очистку), сверка копии, SKU, паспорта и SHA, `apply_migration.vet` её
    принимает, файл — отпечатком.

Запуск (pytest не нужен):  python tests/test_passport_conflicts.py
"""
from __future__ import annotations

import copy as _copy
import hashlib
import io
import pathlib
import re
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import passport_decisions as pdec  # noqa: E402
from services import passport_facts as pf  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def _p(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"


def _tbl(rows):
    return "<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc>{_p(c)}</w:tc>" for c in r) + "</w:tr>"
                               for r in rows) + "</w:tbl>"


def passport(conflicts, head=("ID", "Поле", "Сторона A", "Сторона B", "Статус")):
    """Паспорт в форме v2 99601000-B: комплект с АКБ, конфликт комплектации."""
    body = (_p("Паспорт SKU 99601000-B", "Title")
            + _tbl([("Параметр", "Значення"), ("passport_id", "PASS-99601000-B-001"), ("passport_version", "2"),
                    ("state", "NOT_READY"), ("sku_id", "99601000-B")])
            + _p("Ідентичність товару", "Heading1")
            + _tbl([("Поле", "Значення", "Статус", "Джерело"), ("Модель", "DVB-200BC Dual", "PROPOSED", "SRC-1")])
            + _p("Комплектація та функціональні елементи", "Heading1")
            + _tbl([("ID", "Елемент", "Кількість", "Статус", "Джерело"),
                    ("KIT-1", "Колеса", "1", "PROPOSED", "SRC-3"),
                    ("KIT-10", "Акумулятор BP-240 4 Ah", "2", "PROPOSED", "SRC-5")])
            + _p("Технічні характеристики", "Heading1")
            + _tbl([("ID", "Характеристика", "Значення", "Статус", "Джерело"),
                    ("FACT-6", "Живлення", "20 В; номінальна 36 В", "PROPOSED", "SRC-1"),
                    ("FACT-13", "Об’єм мішка", "45 л", "PROPOSED", "SRC-1")])
            + _p("Конфлікти", "Heading1")
            + _tbl([head] + [tuple(c) for c in conflicts]))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                   f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    return b.getvalue()


KIT = ("CONFLICT-2", "Комплектація АКБ і ЗП", "UA: без АКБ та ЗП", "Marketplace: 2× BP-240 4 Ah + FC-230 Dual")
VOLT = ("CONFLICT-3", "Напруга", "20 В platform; 36 В nominal", "Marketplace: 20 V")


def run(status_kit, status_volt="OPEN_OWNER_DECISION", decisions=None):
    f = pf.read(passport([KIT + (status_kit,), VOLT + (status_volt,)]))
    if decisions:
        pf.apply_decisions(f, decisions)
    text = f.prompt_text()
    return f, text


# ------------------------------------------------------------------ 1. статусы
print("1. статус конфликта")
for s in ("OPEN_OWNER_DECISION", "OPEN_MARKET_SCOPE_DECISION", "OPEN_EVIDENCE_DECISION", "", "  ", "UNKNOWN",
          "RESOLVD", "NEEDS_DECISION", "закрито", None,
          # «только явно» (проверка #176): начало целым словом, без «ещё не решено»
          "RESOLVEDX", "DECIDEDLY_OPEN", "RESOLVED_PENDING_OWNER", "CLOSED_REOPENED", "DECIDED_NOT_YET", "SCOPED",
          "CLOSED-REOPEN", "RESOLVED UNRESOLVED"):
    check(f"статус {s!r} — открытый", not pf.is_closed_status(s))
for s in ("RESOLVED", "RESOLVED_BY_OWNER", "CLOSED", "closed_evidence", "DECIDED", "DECIDED_SIDE_B", "SCOPED_APART",
          " Resolved "):
    check(f"статус {s!r} — закрытый", pf.is_closed_status(s))

f, text = run("OPEN_OWNER_DECISION")
check("открытый конфликт комплекта — KIT-10 с BP-240 вырезан, в «НЕ ИСПОЛЬЗОВАТЬ»",
      any(d.startswith("KIT-10") for d in f.dropped) and "- Комплектація АКБ і ЗП" in text.split("НЕ ИСПОЛЬЗОВАТЬ")[1])
f, text = run("RESOLVED_BY_OWNER")
check("закрытый в паспорте конфликт значений не вырезает: KIT-10 в модели",
      not any(d.startswith("KIT-10") for d in f.dropped) and "Акумулятор BP-240 4 Ah" in text)
check("закрытый в паспорте — не в «НЕ ИСПОЛЬЗОВАТЬ», открытый «Напруга» — там",
      "Комплектація АКБ і ЗП" not in text.split("НЕ ИСПОЛЬЗОВАТЬ")[1] and "- Напруга" in text)
check("открытый «Напруга» по-прежнему вырезает FACT-6", any(d.startswith("FACT-6") for d in f.dropped))
f, _ = run("RESOLVD")
check("опечатка в статусе — конфликт открыт, KIT-10 вырезан", any(d.startswith("KIT-10") for d in f.dropped))

# ------------------------------------------------------------------ 2. решения
print("2. решения верификатора")
DEC_B = {"CONFLICT-2": {"decision": "SIDE_B", "decision_source": "чат 21.10, Ярослав", "value": None}}
f, text = run("OPEN_OWNER_DECISION", decisions=DEC_B)
check("решение «сторона B» — KIT-10 в модели, конфликт не в «НЕ ИСПОЛЬЗОВАТЬ»",
      "Акумулятор BP-240 4 Ah" in text and "Комплектація АКБ і ЗП" not in text.split("НЕ ИСПОЛЬЗОВАТЬ")[1])
check("решённое значение — разделом «РЕШЕНИЯ ПО КОНФЛИКТАМ» со стороной B",
      "## РЕШЕНИЯ ПО КОНФЛИКТАМ" in text and "- Комплектація АКБ і ЗП: Marketplace: 2× BP-240 4 Ah + FC-230 Dual" in text)
check("решённый конфликт — не открыт, но и не «закрыт в паспорте»",
      not pf.is_open(f.conflicts[0]) and not pf.is_closed_status(f.conflicts[0]["status"]))
f, text = run("OPEN_OWNER_DECISION", decisions={"CONFLICT-2": {"decision": "SIDE_B", "value": "2× BP-240 4Ah + FC-230 Dual",
                                                               "decision_source": "чат 21.10, Ярослав"}})
check("у стороны записано чистое значение — в модель идёт оно, без комментария стороны",
      "- Комплектація АКБ і ЗП: 2× BP-240 4Ah + FC-230 Dual" in text)
f, text = run("OPEN_OWNER_DECISION", decisions={"CONFLICT-3": {"decision": "SIDE_B", "decision_source": "чат 22.10, Ярослав"}})
check("решение «20 V» по напряжению: «36 В» отвергнутой стороны по-прежнему вырезает FACT-6",
      any(d.startswith("FACT-6") for d in f.dropped) and "36в" in ", ".join(f.dropped))
f, text = run("OPEN_OWNER_DECISION", decisions={"CONFLICT-2": {"decision": "VALUE", "value": "без АКБ та ЗП",
                                                               "decision_source": "чат 21.10, Ярослав"}})
check("своё значение «без АКБ» — BP-240 стороны B вырезан, решение в модели",
      any(d.startswith("KIT-10") for d in f.dropped) and "- Комплектація АКБ і ЗП: без АКБ та ЗП" in text)
f, text = run("OPEN_OWNER_DECISION", decisions={"CONFLICT-99": dict(DEC_B["CONFLICT-2"])})
check("решение по конфликту, которого в копии нет, не применяется",
      any(d.startswith("KIT-10") for d in f.dropped) and "РЕШЕНИЯ" not in text)
f, text = run("OPEN_OWNER_DECISION", decisions={"CONFLICT-2": {"decision": "MAYBE", "decision_source": "x" * 9}})
check("неизвестный вид решения не применяется: конфликт открыт, раздела решений нет",
      any(d.startswith("KIT-10") for d in f.dropped) and not f.conflicts[0].get("decision")
      and pf.is_open(f.conflicts[0]) and "РЕШЕНИЯ" not in text and "- Комплектація АКБ і ЗП" in text)
f = pf.read(passport([KIT + ("OPEN_OWNER_DECISION",), VOLT + ("OPEN_OWNER_DECISION",)]))
pf.apply_decisions(f, DEC_B)
open_f, dropped, decided = pf.conflict_summary(f)
check("сводка для экрана: решённый — не среди открытых, а отдельно, со значением и источником",
      open_f == ["Напруга"] and decided == [("Комплектація АКБ і ЗП", "Marketplace: 2× BP-240 4 Ah + FC-230 Dual",
                                            "чат 21.10, Ярослав")] and any(d.startswith("FACT-6") for d in dropped))
PAGE = (ROOT / "pages" / "textgen.py").read_text(encoding="utf-8")
check("генератор берёт открытые и решённые из этой же сводки, своей логики не держит",
      "pf.conflict_summary(facts)" in PAGE and "pf.is_open(" not in PAGE)
check("токены CONFLICT_VALUE: после «сторона B» значения B разрешены",
      "bp-240" not in pf.conflict_tokens(run("OPEN_X", decisions=DEC_B)[0].conflicts)
      and "bp-240" in pf.conflict_tokens(run("OPEN_X")[0].conflicts))

# ------------------------------------------------------------------ 3. шапка таблицы
print("3. таблица «Конфлікти» по шапке")
f = pf.read(passport([("CONFLICT-2", "OPEN_X", "Комплект", "чат 21.10", "без АКБ", "2 АКБ")],
                     head=("ID", "Статус", "Поле", "Джерело рішення", "Сторона A", "Сторона B")))
c = f.conflicts[0]
check("колонки по шапке, а не по местам; источник решения прочитан",
      (c["id"], c["status"], c["field"], c["a"], c["b"], c["source"]) ==
      ("CONFLICT-2", "OPEN_X", "Комплект", "без АКБ", "2 АКБ", "чат 21.10"))
f = pf.read(passport([KIT + ("OPEN_OWNER_DECISION",)]))
check("шапка v2 (5 колонок) — как раньше, источник пуст",
      (f.conflicts[0]["status"], f.conflicts[0]["source"]) == ("OPEN_OWNER_DECISION", ""))

# ------------------------------------------------------------------ 4. сервис решений
print("4. сервис решений")
f = pf.read(passport([KIT + ("OPEN_OWNER_DECISION",)]))
check("без источника — NO_SOURCE", pdec.check(f, "CONFLICT-2", "SIDE_B", "", "чат") == "NO_SOURCE")
check("источник из пробелов — NO_SOURCE", pdec.check(f, "CONFLICT-2", "SIDE_B", "", "     ") == "NO_SOURCE")
check("своё значение без значения — NO_VALUE", pdec.check(f, "CONFLICT-2", "VALUE", " ", "чат 21.10, Ярослав") == "NO_VALUE")
check("чужой конфликт — NO_CONFLICT", pdec.check(f, "CONFLICT-9", "SIDE_B", "", "чат 21.10, Ярослав") == "NO_CONFLICT")
check("неизвестный вид — BAD_DECISION", pdec.check(f, "CONFLICT-2", "BOTH", "", "чат 21.10, Ярослав") == "BAD_DECISION")
check("верное решение — без причины", pdec.check(f, "CONFLICT-2", "SIDE_B", "", "чат 21.10, Ярослав") is None)


class Conn:
    def __init__(self):
        self.sql, self.params = [], []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self

    def execute(self, sql, p=()):
        self.sql.append(sql)
        self.params.append(p)

    def fetchone(self):
        return (17,)

    def fetchall(self):
        return [(1, "CONFLICT-2", "SIDE_A", None, "чат 20.10, Ярослав", "a@x", None),
                (5, "CONFLICT-2", "SIDE_B", None, "чат 21.10, Ярослав", "a@x", None),
                (3, "CONFLICT-3", "VALUE", "20V", "чат 21.10, Ярослав", "a@x", None)]


cn = Conn()
new = pdec.record(cn, copy={"source_artifact_id": "DOCX-PASS-1-v2", "sha256": "a" * 64}, sku="99601000-B",
                  passport_id="PASS-1", conflict_id="CONFLICT-2", decision="SIDE_B", value="  ",
                  source="  чат   21.10,  Ярослав ", actor="y@dniprom.com")
check("запись — один INSERT, id из RETURNING", new == 17 and len(cn.sql) == 1 and cn.sql[0].startswith(
    "INSERT INTO passport_conflict_decisions") and "RETURNING id" in cn.sql[0])
check("пустое значение стороны — NULL, источник без лишних пробелов, копия и SHA переданы",
      cn.params[0][6] is None and cn.params[0][7] == "чат 21.10, Ярослав"
      and cn.params[0][:4] == ("DOCX-PASS-1-v2", "a" * 64, "99601000-B", "PASS-1"))


class Cur(Conn):
    def __init__(self, table=True):
        super().__init__()
        self.table = table

    def fetchone(self):
        return (self.table,)


cur = Cur()
got = pdec.read_with(cur, "DOCX-PASS-1-v2", "a" * 64)
check("чтение для генерации: действует последнее решение по конфликту",
      got["CONFLICT-2"]["decision"] == "SIDE_B" and got["CONFLICT-3"]["value"] == "20V")
check("чтение — по копии и её SHA", cur.params[1] == {"a": "DOCX-PASS-1-v2", "s": "a" * 64}
      and "artifact_sha256 = %(s)s" in cur.sql[1])
check("нет таблицы — решений нет, запроса к ней нет", pdec.read_with(Cur(table=False), "x", "y") == {})
SRC = (ROOT / "services" / "passport_decisions.py").read_text(encoding="utf-8")
check("сервис не меняет и не удаляет решений", not re.search(r"\bUPDATE\b|\bDEL" + r"ETE\b", SRC))

# ------------------------------------------------------------------ 5. генерация
print("5. генерация берёт решения до вызова модели")
from services import textgen as tg  # noqa: E402

DOCX = passport([KIT + ("OPEN_OWNER_DECISION",)])
SHA = hashlib.sha256(DOCX).hexdigest()


class Store:
    def get(self, loc):
        return DOCX


class GenDB:
    def __init__(self, decisions):
        self.decisions, self.calls, self.content, self.order = decisions, [], [], []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self

    def execute(self, sql, p=()):
        self.order.append(sql.split()[0] + " " + sql.split()[1])
        if sql.startswith("SELECT to_regclass('listing_data.passport_conflict_decisions')"):
            self.res = [(True,)]
        elif "FROM passport_conflict_decisions" in sql:
            self.res = [(i, d["cid"], d["kind"], d.get("value"), "чат 21.10, Ярослав", "y", None)
                        for i, d in enumerate(self.decisions, 1) if (d["aid"], d["sha"]) == (p["a"], p["s"])]
        elif "pg_advisory_xact_lock" in sql or sql.startswith("SELECT to_regclass"):
            self.res = [(True,)]
        elif "information_schema.columns" in sql:
            self.res = [(2,)]
        elif sql.startswith("SELECT count(*)"):
            self.res = [(0, 0, 0)]
        elif sql.startswith("INSERT INTO textgen_calls"):
            self.calls.append(p)
            self.res = [(1,)]
        elif sql.startswith("SELECT COALESCE(max(version)"):
            self.res = [(0,)]
        else:
            self.res = []

    def fetchone(self):
        return self.res[0] if self.res else None

    def fetchall(self):
        return list(self.res)


def gen(decisions):
    seen = {}

    def ai_call(task, prompt, system=None):
        seen["prompt"] = prompt
        return None          # ответ не важен: проверяется, что ушло в модель

    db = GenDB(decisions)
    tg.generate(sku="99601000-B", marketplace="es", copy={"source_artifact_id": "DOCX-PASS-99601000-B-001-v2",
                "passport_id": "PASS-99601000-B-001", "archived_locator": "/Volumes/x", "sha256": SHA},
                actor="y", store=Store(), conn=db, method=("методология", 1), provider="anthropic",
                model="claude-opus-5-5", max_tokens=100, setting=lambda k, d="": d, ai_call=ai_call,
                ai_usage=lambda: {}, ai_reset=lambda: None, asins=["B0GTRY26HB"])
    return seen.get("prompt", ""), db


prompt, db = gen([])
check("без решений — KIT-10 не в модели, конфликт в «НЕ ИСПОЛЬЗОВАТЬ»",
      "Акумулятор BP-240" not in prompt and "НЕ ИСПОЛЬЗОВАТЬ" in prompt)
prompt, db = gen([{"cid": "CONFLICT-2", "kind": "SIDE_B", "aid": "DOCX-PASS-99601000-B-001-v2", "sha": SHA}])
check("решение «сторона B» по этой копии — KIT-10 и решение в промпте",
      "Акумулятор BP-240 4 Ah" in prompt and "РЕШЕНИЯ ПО КОНФЛИКТАМ" in prompt)
check("решения читаются до резерва и вызова модели",
      db.order.index("SELECT id,") < db.order.index("INSERT INTO"))
prompt, _ = gen([{"cid": "CONFLICT-2", "kind": "SIDE_B", "aid": "DOCX-PASS-99601000-B-001-v3", "sha": "b" * 64}])
check("решение по другой копии (v3, другой SHA) не действует", "Акумулятор BP-240" not in prompt)

# ------------------------------------------------------------------ 6. миграция
print("6. миграция таблицы решений")
MIG = ROOT / "migrations" / pdec.MIGRATION
raw = MIG.read_bytes()
SQL = re.sub(r"\s+", " ", "\n".join(line.split("--")[0] for line in raw.decode("utf-8").splitlines())).strip()
check("файл миграции назван сервисом и существует", MIG.is_file())
check("без блочных комментариев /* */", b"/*" not in raw and b"*/" not in raw)
check("одна транзакция", SQL.count("BEGIN;") == 1 and SQL.count("COMMIT;") == 1 and SQL.index("BEGIN;") < SQL.index("COMMIT;"))
check("решение — сторона A, сторона B или своё значение", "CHECK (decision IN ('SIDE_A', 'SIDE_B', 'VALUE'))" in SQL)
check("своё значение обязано быть", "CHECK ( decision <> 'VALUE' OR (value IS NOT NULL AND btrim(value) <> ''))" in SQL)
check("источник решения — не короче 5 знаков", "CHECK (char_length(btrim(decision_source)) >= 5)" in SQL)
check("ссылка на копию и её SHA", "REFERENCES listing_data.passport_source_artifacts (source_artifact_id)" in SQL
      and "artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[a-f0-9]{64}$')" in SQL)
body = re.search(r"FUNCTION listing_data\.passport_conflict_decisions_guard\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$(.*?)\$\$;", SQL)
B = body.group(1) if body else ""
check("правка и удаление строки — исключение (только дописывание)",
      B.strip().startswith("DECLARE") and "IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION" in B)
check("копия действующая, SKU, паспорт и SHA совпадают с копией — иначе исключение",
      "IF copy_life IS DISTINCT FROM 'ACTIVE' THEN RAISE EXCEPTION" in B
      and "copy_sku IS DISTINCT FROM NEW.sku_id OR copy_pass IS DISTINCT FROM NEW.passport_id OR copy_sha IS DISTINCT FROM NEW.artifact_sha256" in B
      and "FOR SHARE;" in B)
check("ровно один выход RETURN NEW — после всех проверок", B.count("RETURN NEW;") == 1
      and B.index("RETURN NEW;") > B.index("NEW.decided_at > now()"))
check("время решения — сейчас: ни в будущем, ни задним числом (проверка #176)",
      "IF NEW.decided_at > now() + interval '5 minutes' OR NEW.decided_at < now() - interval '5 minutes' THEN RAISE EXCEPTION" in B)
check("триггер на строки (вставка, правка, удаление) и на очистку таблицы",
      "BEFORE INSERT OR UPDATE OR DELETE ON listing_data.passport_conflict_decisions FOR EACH ROW" in SQL
      and "BEFORE TRUNC" + "ATE ON listing_data.passport_conflict_decisions FOR EACH STATEMENT" in SQL)
check("исключения — исключения, ничего не выключается", not re.search(r"RAISE (NOTICE|WARNING|INFO|LOG|DEBUG)", SQL)
      and not re.search(r"\b(DISABLE|REPLICA|session_replication_role|ALTER TABLE|DEL" + r"ETE FROM|RENAME)\b", SQL, re.I))
sys.path.insert(0, str(ROOT / "scratchpad"))
import apply_migration as am  # noqa: E402

try:
    am.vet(MIG)
    vet_ok = True
except SystemExit:
    vet_ok = False
check("scratchpad/apply_migration.py принимает файл", vet_ok)
check("файл не менялся без осознанной правки отпечатка",
      hashlib.sha256(raw).hexdigest() == "e4044d5364efc2bda78f64ec7de39116505ae1b431649aade73c99e7e6997733")

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
