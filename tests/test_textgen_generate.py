# -*- coding: utf-8 -*-
"""
tests/test_textgen_generate.py — генерация текстов по паспорту SKU
(`services/textgen.py`, `services/passport_facts.py`; решение владельца 21.10.2026).
Без сети и базы: том, база и модель подменены, паспорт собирается в тесте.

Что заперто:
  · в модель идут только разделы-факты паспорта; «Конфлікти» — не идут, их поля
    названы списком «НЕ ИСПОЛЬЗОВАТЬ»; колонки источников — не идут;
  · лимиты владельца: 10 вызовов на товар в сутки, $1 на товар, $10 на пилот;
    перед вызовом резервируется оценка сверху, после — фактическая цена;
    при превышении — отказ ДО вызова модели и без записи;
  · цена модели неизвестна или методологии нет — отказ до чтения тома и записи;
  · копия паспорта сверяется по SHA и по SKU;
  · удачный вызов — 8 черновиков одним предложением TG-<id>, версии растут,
    ссылка на паспорт и копию, проверки правил тайтла кодом;
  · неудачный — вызов учтён (failed) с ценой, черновиков нет.

Запуск (pytest не нужен):  python tests/test_textgen_generate.py
"""
from __future__ import annotations

import copy as _copy
import hashlib
import io
import json
import pathlib
import re
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import passport_facts as pf  # noqa: E402
from services import textgen as tg  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# ------------------------------------------------------------------ паспорт
def _p(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"


def _tbl(rows):
    return "<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc>{_p(c)}</w:tc>" for c in r) + "</w:tr>"
                               for r in rows) + "</w:tbl>"


def passport(sku="99601000-B", ver="2"):
    body = (_p(f"Паспорт SKU {sku}", "Title")
            + _tbl([("Параметр", "Значення"), ("passport_id", "PASS-99601000-B-001"), ("passport_version", ver),
                    ("state", "NOT_READY"), ("sku_id", sku)])
            + _p("Ідентичність товару", "Heading1")
            + _tbl([("Поле", "Значення", "Статус", "Джерело"), ("Модель", "DVB-200BC Dual", "PROPOSED", "SRC-1")])
            + _p("Технічні характеристики", "Heading1")
            + _tbl([("ID", "Характеристика", "Значення", "Статус", "Джерело"),
                    ("FACT-1", "Об’єм мішка", "45 л", "PROPOSED", "SRC-SECRET-77")])
            + _p("Комплектація та функціональні елементи", "Heading1")
            + _tbl([("ID", "Елемент", "Кількість"), ("KIT-1", "Колеса", "1")])
            + _tbl([("ID", "Елемент", "Кількість"), ("KIT-2", "Акумулятор BP-240 4 Ah", "2")])
            + _p("Конфлікти", "Heading1")
            + _tbl([("ID", "Поле", "Сторона A", "Сторона B", "Статус"),
                    ("CONFLICT-1", "Гарантія", "36 місяців", "5 років", "OPEN"),
                    ("CONFLICT-2", "Комплектація АКБ", "без АКБ", "2× BP-240 4 Ah", "OPEN")])
            + _p("Джерела і походження", "Heading1")
            + _tbl([("source_id", "Назва"), ("SRC-1", "Офіційна картка")]))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                   f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    return b.getvalue()


DOCX = passport()
facts = pf.read(DOCX)
text = facts.prompt_text()
check("разделы-факты прочитаны, служебные и конфликты — нет",
      [s.title for s in facts.sections] == ["Ідентичність товару", "Технічні характеристики",
                                            "Комплектація та функціональні елементи"])
check("факты в промпте: модель, мешок, комплект", all(x in text for x in ("DVB-200BC Dual", "45 л", "Колеса")))
check("стороны конфликта в промпт не идут", "36 місяців" not in text and "5 років" not in text)
check("поле конфликта названо списком «НЕ ИСПОЛЬЗОВАТЬ»", "НЕ ИСПОЛЬЗОВАТЬ" in text and "- Гарантія" in text)
check("колонки источников и раздел источников в промпт не идут",
      "SRC-SECRET-77" not in text and "Офіційна картка" not in text)
check("конфликты для экрана", facts.conflicts[0]["field"] == "Гарантія")
check("строка факта со значением стороны конфликта снята кодом (не только словами модели)",
      "BP-240" not in text and "4 Ah" not in text and any(d.startswith("KIT-2") for d in facts.dropped))
check("соседняя строка без значений конфликта осталась", "Колеса" in text)
check("модель из раздела идентичности", tg.model_code(facts) == "DVB-200BC Dual")
prompt = tg.build_prompt("99601000-B", "es", {"passport_id": "PASS-X", "passport_version": "2", "state": "NOT_READY"}, facts)
check("язык площадки назван в промпте", "español" in prompt and "Amazon ES" in prompt)

# ------------------------------------------------------------------ цена и лимиты
check("цены по справочнику: Opus 5.5 $4/$20, Sonnet 5 $2/$10",
      tg.price("claude-opus-5-5") == (4.0, 20.0) and tg.price("claude-sonnet-5") == (2.0, 10.0))
check("запись в кэш — по 2× входа, чтение — по полной цене входа",
      tg.usage_cost((4.0, 20.0), {"input_tokens": 1000, "cache_creation_input_tokens": 1000,
                                  "cache_read_input_tokens": 1000, "output_tokens": 0})[2] == tg.cost((4.0, 20.0), 4000, 0))
check("цена из настройки «вход/выход»", tg.price("x", lambda k, d="": "2/10" if k == "price.x" else d) == (2.0, 10.0))
check("неизвестная модель — цены нет", tg.price("unknown-model") is None)
check("стоимость: 1M входа по $3 + 0,1M выхода по $15", tg.cost((3.0, 15.0), 1_000_000, 100_000) == 4.5)
check("оценка сверху — весь бюджет ответа", tg.estimate((3.0, 15.0), 10_000, 8000) >= 0.12)
check("10 вызовов — отказ", tg.block_reason(tg.Usage(calls_sku=10), 0.01)[0] == "LIMIT_CALLS")
check("$1 на товар с оценкой — отказ", tg.block_reason(tg.Usage(calls_sku=1, usd_sku=0.95), 0.1)[0] == "LIMIT_USD_SKU")
check("$10 на пилот с оценкой — отказ", tg.block_reason(tg.Usage(usd_pilot=9.95), 0.1)[0] == "LIMIT_USD_PILOT")
check("в пределах — можно", tg.block_reason(tg.Usage(calls_sku=9, usd_sku=0.5, usd_pilot=5), 0.1) is None)
check("сутки — по Киеву", "Europe/Kyiv" in tg.DAY_START)


# ------------------------------------------------------------------ подмены
class DB:
    def __init__(self):
        self.calls, self.content, self.log = [], [], []
        self.fail_content = False
        self.no_content_table = False

    def cursor(self):
        return Cur(self)

    def __enter__(self):
        self.snap = _copy.deepcopy((self.calls, self.content))
        return self

    def __exit__(self, et, *a):
        if et is not None:
            self.calls, self.content = self.snap
        return False


class Cur:
    def __init__(self, db):
        self.db, self.res = db, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, p=()):
        db = self.db
        db.log.append(sql.split()[0] + " " + " ".join(sql.split()[1:3]))
        if "pg_advisory_xact_lock" in sql:
            self.res = [(None,)]
        elif sql.startswith("SELECT to_regclass"):
            self.res = [(not db.no_content_table,)]
        elif sql.startswith("SELECT count(*)"):
            today = [c for c in db.calls if not c.get("yesterday")]
            self.res = [(sum(1 for c in today if c["sku"] == p[0]),
                         sum(c["cost_usd"] for c in today if c["sku"] == p[1]),
                         sum(c["cost_usd"] for c in today))]
        elif sql.startswith("INSERT INTO textgen_calls"):
            row = dict(zip(("sku", "marketplace", "actor", "provider", "model", "cost_usd"), p),
                       id=len(db.calls) + 1, status="started")
            db.calls.append(row)
            self.res = [(row["id"],)]
        elif sql.startswith("UPDATE textgen_calls"):
            row = next(c for c in db.calls if c["id"] == p[-1])
            row.update(status=p[0], input_tokens=p[1], output_tokens=p[2], cost_usd=p[3], proposal_id=p[4],
                       error=p[5])
            self.res = []
        elif sql.startswith("SELECT COALESCE(max(version)"):
            vs = [c["version"] for c in db.content if (c["sku"], c["marketplace"], c["field"]) == tuple(p)]
            self.res = [(max(vs, default=0),)]
        elif sql.startswith("INSERT INTO content_versions"):
            if db.fail_content:
                raise RuntimeError("content_versions: триггер отказал")
            cols = re.search(r"\((.*?)\) VALUES", sql).group(1).replace(" ", "").split(",")
            vals = list(p[:11]) + ["model"] + list(p[11:])
            db.content.append(dict(zip(cols, vals)))
            self.res = []
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self.res[0] if self.res else None


class Store:
    def __init__(self, data):
        self.data, self.reads = data, 0

    def get(self, loc):
        self.reads += 1
        return self.data


COPY = {"source_artifact_id": "DOCX-PASS-99601000-B-001-v2", "passport_id": "PASS-99601000-B-001",
        "archived_locator": "/Volumes/x/v2.docx", "sha256": hashlib.sha256(DOCX).hexdigest()}
GOOD = {"title": "DNIPRO-M Aspirador Soplador de Hojas, Aire 245km/h, Tritura 15:1, Bolsa 45L",
        "highlight": "Model DVB-200BC Dual: soplador aspirador de hojas con batería, motor brushless",
        "bullets": [f"VALOR {i}: texto" for i in range(1, 6)], "description": "Descripción."}
USAGE = {"input_tokens": 9000, "output_tokens": 1200}


def run(db, *, answer=GOOD, usage=USAGE, store=None, method=("методология", 3), model="claude-opus-5-5",
        copy=COPY, raise_in_call=False, provider="anthropic"):
    seen = {"calls": 0, "during": None}

    def ai_call(task, prompt, system=None):
        seen["calls"] += 1
        seen["during"] = [dict(c) for c in db.calls]       # что лежит в журнале в момент вызова
        seen["task"], seen["system"], seen["prompt"] = task, system, prompt
        if raise_in_call:
            raise TimeoutError("нет ответа")
        return answer

    res = tg.generate(sku="99601000-B", marketplace="es", copy=copy, actor="yaroslav@dniprom.com",
                      store=store or Store(DOCX), conn=db, method=method, provider=provider, model=model,
                      max_tokens=8000, setting=lambda k, d="": d, ai_call=ai_call,
                      ai_usage=lambda: dict(usage), ai_reset=lambda: None, ai_error=lambda: "разбор не удался")
    return res, seen


db = DB()
res, seen = run(db)
call = db.calls[0] if db.calls else {}
check("удача: OK, предложение TG-<id>", res.status == "OK" and res.proposal_id == "TG-1")
check("до вызова в журнале — резерв started с оценкой сверху",
      seen["during"] and seen["during"][0]["status"] == "started"
      and seen["during"][0]["cost_usd"] == tg.estimate((4.0, 20.0), len(seen["prompt"]) + len("методология"), 8000))
check("после — фактическая цена по расходу токенов", call.get("status") == "ok"
      and call.get("cost_usd") == tg.cost((4.0, 20.0), 9000, 1200) and call.get("proposal_id") == "TG-1")
check("методология textgen — постоянной частью (system), задача textgen",
      seen["task"] == "textgen" and seen["system"] == "методология")
check("8 черновиков, одним предложением, версия 1",
      sorted(c["field"] for c in db.content) == sorted(tg.FIELDS)
      and {c["proposal_id"] for c in db.content} == {"TG-1"} and {c["version"] for c in db.content} == {1})
t0 = next(c for c in db.content if c["field"] == "title")
check("черновик: текст, автор, модель, версия методологии, паспорт и копия",
      t0["text"] == GOOD["title"] and t0["created_by"] == "yaroslav@dniprom.com" and t0["model"] == "claude-opus-5-5"
      and t0["skill_version"] == 3 and t0["passport_id"] == "PASS-99601000-B-001" and t0["passport_version"] == "2"
      and t0["passport_sha256"] == COPY["sha256"] and t0["passport_artifact_id"] == COPY["source_artifact_id"]
      and t0["origin"] == "model")
b5 = next(c for c in db.content if c["field"] == "bullet_5")
check("буллеты по полям", b5["text"] == "VALOR 5: texto")
check("проверки правил тайтла записаны кодом (чистый тайтл — пусто)", json.loads(t0["checks"]) == [])
res2, _ = run(db, answer={**GOOD, "title": "Aspirador DNIPRO-M | Soplador!"})
t2 = [c for c in db.content if c["field"] == "title" and c["version"] == 2]
check("второй вызов — версия 2, нарушения тайтла названы",
      res2.status == "OK" and t2 and {v["code"] for v in json.loads(t2[0]["checks"])} >= {"BRAND_NOT_FIRST", "FORBIDDEN_CHAR"})

# --- лимиты: отказ ДО модели и без записи
db = DB()
db.calls = [{"id": i + 1, "sku": "99601000-B", "cost_usd": 0.01, "status": "ok"} for i in range(10)]
res, seen = run(db)
check("10 вызовов сегодня — BLOCKED LIMIT_CALLS, модель не вызвана, журнал не тронут",
      res.status == "BLOCKED" and res.code == "LIMIT_CALLS" and seen["calls"] == 0 and len(db.calls) == 10)
db = DB()
db.calls = [{"id": i + 1, "sku": "99601000-B", "cost_usd": 0.01, "status": "ok", "yesterday": True} for i in range(10)]
res, seen = run(db)
check("вчерашние вызовы не в счёт", res.status == "OK")
db = DB()
db.calls = [{"id": 1, "sku": "99601000-B", "cost_usd": 0.95, "status": "ok"}]
res, seen = run(db)
check("$1 на товар — BLOCKED LIMIT_USD_SKU до вызова", res.code == "LIMIT_USD_SKU" and seen["calls"] == 0)
db = DB()
db.calls = [{"id": 1, "sku": "OTHER", "cost_usd": 9.95, "status": "ok"}]
res, seen = run(db)
check("$10 на пилот — BLOCKED LIMIT_USD_PILOT до вызова", res.code == "LIMIT_USD_PILOT" and seen["calls"] == 0)
db = DB()
db.calls = [{"id": 1, "sku": "99601000-B", "cost_usd": 0.9, "status": "started"}]
res, seen = run(db)
check("незавершённый вызов держит свой резерв в лимите", res.code == "LIMIT_USD_SKU")

# --- отказы до тома и записи
db, st_ = DB(), Store(DOCX)
res, seen = run(db, method=("", 0), store=st_)
check("методологии нет — BLOCKED NO_METHOD, том не читался, записи нет",
      res.code == "NO_METHOD" and st_.reads == 0 and not db.calls and seen["calls"] == 0)
db, st_ = DB(), Store(DOCX)
res, seen = run(db, model="unknown-model", store=st_)
check("цены нет — BLOCKED NO_PRICE до тома и записи", res.code == "NO_PRICE" and st_.reads == 0 and not db.calls)
db = DB()
res, seen = run(db, store=Store(DOCX + b"x"))
check("копия в томе не сходится по SHA — FAILED COPY_CHANGED, записи нет",
      res.code == "COPY_CHANGED" and not db.calls and seen["calls"] == 0)
db = DB()
other = passport(sku="21680000")
res, seen = run(db, store=Store(other), copy={**COPY, "sha256": hashlib.sha256(other).hexdigest()})
check("копия другого SKU — FAILED COPY_OTHER_SKU", res.code == "COPY_OTHER_SKU" and not db.calls)

db, st_ = DB(), Store(DOCX)
res, seen = run(db, provider="gemini", store=st_)
check("не Anthropic — BLOCKED PROVIDER до тома и записи (расход размышления не считается)",
      res.code == "PROVIDER" and st_.reads == 0 and not db.calls)
db = DB()
res, seen = run(db, copy={**COPY, "passport_id": "PASS-OTHER"})
check("в копии другой паспорт — FAILED COPY_OTHER_PASSPORT до записи", res.code == "COPY_OTHER_PASSPORT" and not db.calls)
db = DB()
db.no_content_table = True
res, seen = run(db)
check("нет таблицы черновиков — BLOCKED до вызова и без резерва",
      res.code == "NO_CONTENT_TABLE" and seen["calls"] == 0 and not db.calls)
db = DB()
res, seen = run(db, answer={**GOOD, "bullets": GOOD["bullets"][:4] + ["INCLUYE: 2 baterías BP-240 de 4Ah"]})
b5c = next(c for c in db.content if c["field"] == "bullet_5")
check("значение конфликта в ответе — нарушение CONFLICT_VALUE в checks поля",
      res.status == "OK" and any(v["code"] == "CONFLICT_VALUE" for v in json.loads(b5c["checks"])))

# --- неудачный вызов: учтён, черновиков нет
db = DB()
res, seen = run(db, answer={"title": "x"})
check("ответ не в формате — FAILED MODEL, вызов failed с ценой, черновиков нет",
      res.code == "MODEL" and db.calls[0]["status"] == "failed" and db.calls[0]["cost_usd"] > 0 and not db.content)
db = DB()
res, seen = run(db, raise_in_call=True, usage={})
check("исключение без расхода — списана оценка, а не ноль",
      res.code == "MODEL" and db.calls[0]["status"] == "failed"
      and db.calls[0]["cost_usd"] == seen["during"][0]["cost_usd"] > 0)
db = DB()
db.fail_content = True
try:
    run(db)
    raised = False
except RuntimeError:
    raised = True
check("сбой записи черновиков — исключение наверх, но вызов уже учтён как ok с ценой",
      raised and db.calls[0]["status"] == "ok" and db.calls[0]["cost_usd"] > 0 and not db.content)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
