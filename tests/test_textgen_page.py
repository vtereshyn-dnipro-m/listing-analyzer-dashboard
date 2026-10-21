# -*- coding: utf-8 -*-
"""
tests/test_textgen_page.py — «Генератор текстов (пилот)», шаг 4: каркас без модели.

Проверяется то, что ломается тихо:

  · страница говорит ТО ЖЕ, что правила. Нарушения на экране — ровно те, что
    вернул `title_rules.check()` на тот же текст; своей логики проверки у
    страницы нет, иначе экран и будущая генерация разойдутся;
  · вольтаж в Highlights у инструмента — не нарушение (решение 21.10.2026), а в
    тайтле — нарушение; страница не путает поля;
  · расхождение карточки (DHR-202BC: 4 Ah в атрибуте, 6Ah в наборе) названо
    вслух, а не выбрано молча;
  · сбой чтения — ошибка с причиной, а не пустая карточка «характеристик нет»;
  · ключи по типу: сбой SQP — ошибка, а не «данных поиска нет»;
  · модель не вызывается вовсе; в базу пишет только загрузка паспорта, под правом;
  · колонки таблиц — технические имена (правило 3), подписи из `t()`;
  · SQL роли для базы Кабинета: роль в обоих CHECK, генератор — только админу
    и роли пилота, остальное роли пилота закрыто явными строками, почта не
    подставлена — файл отказывается выполняться.

Сеть и база не трогаются: чтения подменены данными `tests/fixture_pilot.py`.

Запуск (pytest не нужен):  python tests/test_textgen_page.py
"""
from __future__ import annotations

import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from fixture_pilot import PILOT  # noqa: E402

import auth  # noqa: E402
import i18n  # noqa: E402
from services import ai  # noqa: E402
from services import product_specs as ps  # noqa: E402
from services import seo  # noqa: E402
from services import title_rules as tr  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


PAGE = ROOT / "pages" / "textgen.py"
SRC = PAGE.read_text(encoding="utf-8")

# --- подмены: чтения из фикстуры, модель — ловушка ---------------------------
STATE = {"load_err": None, "keys_err": None, "keys": None, "ai_calls": []}


def fake_load(asin, mp):
    if STATE["load_err"]:
        return None, STATE["load_err"]
    d = PILOT[asin]
    return {"title": d["title"], "attributes": d["attributes"], "amazon_type": d["amazon_type"],
            "product_information": d.get("product_information") or {},
            "item_highlight": d.get("item_highlight") or ""}, None


def fake_same_type(tool_type, mp):
    if STATE["keys_err"]:
        return None, STATE["keys_err"]
    return ["B0H75P364R", "B0FZFCQN3H", "B0AAAAAAAA"], None


KEYS = pd.DataFrame([
    {"search_query": "amoladora angular", "volume": 9000, "impressions": 500, "clicks": 9,
     "purchases": 2, "asins": 3},
    {"search_query": "radial bosch", "volume": 7000, "impressions": 300, "clicks": 0,
     "purchases": 0, "asins": 2},
])


def fake_keys(asins, mp, title, weeks=8, top_n=30):
    df = KEYS.copy()
    df["tier"] = df.apply(lambda r: seo.guess_tier(r, title), axis=1)
    df["weight"] = df.apply(seo.phrase_weight, axis=1)
    df["in_title"] = df["search_query"].apply(lambda q: seo.phrase_present(q, title))
    return df


ps.load = fake_load
ps.same_type_asins = fake_same_type
seo.build_type_keyword_table = fake_keys
seo.sqp_error = lambda: None
for _name in ("generate_json", "_call_gemini", "_call_anthropic"):
    setattr(ai, _name, lambda *a, _n=_name, **k: STATE["ai_calls"].append(_n))

from streamlit.testing.v1 import AppTest  # noqa: E402


def run(asin=None, title=None, hl=None, lang="ru"):
    at = AppTest.from_file(str(PAGE), default_timeout=60)
    at.session_state["lang"] = lang
    if asin:
        at.session_state["tg-asin"] = asin
    at.run()
    a = asin or "B0H75P364R"
    if title is not None:
        at.text_input(key=f"tg-title-{a}").input(title)
    if hl is not None:
        at.text_area(key=f"tg-hl-{a}").input(hl)
    if title is not None or hl is not None:
        at.run()
    return at


def texts_of(at) -> str:
    parts = []
    for coll in (at.markdown, at.caption, at.error, at.warning, at.success, at.info):
        parts += [str(e.value) for e in coll]
    parts += [f"{m.label}={m.value}" for m in at.metric]
    return "\n".join(parts)


def bullets(at) -> list[str]:
    return [str(m.value) for m in at.markdown if str(m.value).startswith("- **")]


def lab(key, lang="ru", **kw) -> str:
    s = i18n.LANGS[lang][key]
    return s.format(**kw) if kw else s


# ================================================================ первый показ
at = run()
check("страница открывается без исключения", not at.exception)
full = texts_of(at)
check("тип товара назван словами", lab("tg.type.grinder") in full)
check("модель из атрибута", "DGA-201M" in full)
check("нынешний тайтл с длиной", str(len(PILOT["B0H75P364R"]["title"])) in full)
check("ни одного сырого ключа на экране",
      not re.search(r"\btg\.[a-z_]+(\.[A-Za-z_]+)?\b", full))

specs_df = at.dataframe[0].value
check("колонки характеристик — технические имена (правило 3)",
      list(specs_df.columns) == ["field", "value", "src"])
check("у каждого значения назван источник",
      specs_df["src"].map(bool).all() and lab("tg.src.attribute") in set(specs_df["src"]))
check("значения в формате тайтла (Ø без пробела)", "Ø125mm" in set(specs_df["value"]))
check("части для тайтла по таблице типа выведены",
      ", ".join(ps.title_parts(ps.extract("B0H75P364R", "es", **fake_load("B0H75P364R", "es")[0]))) in full)
check("ключи по типу: число наших товаров названо", lab("tg.keys_from", n=3) in full)
check("до ввода текста нарушений не показано", not at.error and not at.success)

# ================================================================ живая проверка
cases = [
    ("инструмент: вольтаж и «!» в тайтле, бренд не первым",
     "Amoladora Dnipro-M DGA-201M 20V, 10000rpm!", ""),
    ("единица через пробел и бренд не в том регистре",
     "Dnipro-M DGA-201M Amoladora Angular, 125 mm", ""),
    ("Highlights без префикса модели", "DNIPRO-M DGA-201M Amoladora Angular, Ø125mm",
     "Velocidad 10000rpm"),
]
for name, title, hl in cases:
    at = run(title=title, hl=hl)
    want = tr.check(title, hl, kind=tr.TOOL, model="DGA-201M" if hl else None)
    shown = bullets(at)
    check(f"{name}: на экране столько же нарушений, сколько у правил ({len(want)})",
          len(shown) == len(want) and len(want) > 0)
    check(f"{name}: каждое нарушение подписано своим кодом",
          all(lab(f"tg.code.{v.code}") in b for v, b in zip(want, shown)))
    check(f"{name}: число в шапке", any(lab("tg.violations", n=len(want)) == str(e.value) for e in at.error))

ok_title = "DNIPRO-M DGA-201M Amoladora Angular, Ø125mm, 10000rpm"
ok_hl = "Model DGA-201M: compatible con baterías 20V, Ø125mm"
check("контрольный текст правилам не нарушает",
      tr.check(ok_title, ok_hl, kind=tr.TOOL, model="DGA-201M") == [])
at = run(title=ok_title, hl=ok_hl)
check("чистый текст — «нарушений нет», не ошибка",
      not at.error and any(lab("tg.all_ok") == str(s.value) for s in at.success))
check("вольтаж в Highlights у инструмента — не нарушение", not bullets(at))

at = run(title="DNIPRO-M DGA-201M Amoladora Angular 20V, Ø125mm")
check("тот же вольтаж в тайтле — нарушение TOOL_VOLTAGE с полем «тайтл»",
      any(lab("tg.code.TOOL_VOLTAGE") in b and lab("tg.where.title") in b for b in bullets(at)))

at = run(title="x" * 80)
check("счётчик длины: 80 / 75 акцентом",
      any("80 / 75" in str(m.value) and "#E8590C" in str(m.value) for m in at.markdown))

# ключи: отметка «есть в тексте» по введённому
at = run(title="DNIPRO-M DGA-201M Amoladora Angular, Ø125mm")
kdf = next(d.value for d in at.dataframe if "query" in d.value.columns)
check("колонки ключей — технические имена",
      list(kdf.columns) == ["query", "volume", "tier", "asins", "typed"])
check("введённый ключ отмечен, невведённый — нет",
      bool(kdf.set_index("query").loc["amoladora angular", "typed"])
      and not bool(kdf.set_index("query").loc["radial bosch", "typed"]))
check("чужой бренд — «не брать»",
      kdf.set_index("query").loc["radial bosch", "tier"] == lab("tg.tier.forbid"))

# модели нет — «нарушений нет» не выдаёт непроверенный префикс за проверенный
_real_load = ps.load


def no_model_load(asin, mp):
    d, e = fake_load(asin, mp)
    d = dict(d, title="Amoladora Angular Dnipro-M 20V", attributes={
        k: v for k, v in d["attributes"].items() if k != "model_name"})
    return d, e


ps.load = no_model_load
st_mod = __import__("streamlit")
st_mod.cache_data.clear()
at = run(title="DNIPRO-M Amoladora Angular, Ø125mm", hl="Velocidad 10000rpm")
check("модели нет: префикс Highlights назван непроверенным",
      any(lab("tg.no_model_prefix") == str(w.value) for w in at.warning))
at = run(title="DNIPRO-M Amoladora Angular, Ø125mm")
check("и без Highlights оговорки нет", not any(lab("tg.no_model_prefix") == str(w.value) for w in at.warning))
ps.load = _real_load
st_mod.cache_data.clear()
at = run(title=ok_title, hl=ok_hl)
check("модель есть — оговорки нет", not any(lab("tg.no_model_prefix") == str(w.value) for w in at.warning))

# ================================================================ расхождение карточки
at = run(asin="B0H75XRDBK")
check("перфоратор: тип назван", lab("tg.type.hammer") in texts_of(at))
warn = "\n".join(str(w.value) for w in at.warning)
check("4 Ah в атрибуте против 6Ah в наборе названо вслух",
      lab("tg.field.capacity_ah") in warn and "4" in warn and "6" in warn)

at = run(asin="B0FZFCQN3H")
check("сетевая болгарка — питание «Сетевой»", lab("tg.corded") in texts_of(at))

# ================================================================ сбои
import streamlit as st  # noqa: E402

st.cache_data.clear()                 # удачные чтения прошлых прогонов законно в кеше
STATE["load_err"] = "OperationalError: база недоступна"
at = run()
check("сбой чтения — ошибка с причиной, страница не падает",
      not at.exception and any("база недоступна" in str(e.value) for e in at.error))
check("и характеристик «нет» не утверждается", lab("tg.no_specs") not in texts_of(at))
STATE["load_err"] = None
at = run()
check("сбой не закеширован: база ответила — карточка на месте",
      not at.error and lab("tg.type.grinder") in texts_of(at))

st.cache_data.clear()
STATE["keys_err"] = "OperationalError: SQP недоступен"
at = run()
full = texts_of(at)
check("сбой ключей — ошибка, а не «данных поиска нет»",
      "SQP недоступен" in full and lab("tg.keys_empty", n=0) not in full)
STATE["keys_err"] = None
at = run()
check("сбой ключей не закеширован", lab("tg.keys_from", n=3) in texts_of(at))

for lang in ("uk", "en"):
    at = run(lang=lang, title="Amoladora 20V!")
    check(f"{lang}: страница открывается, подписи на своём языке",
          not at.exception and lab("tg.type.grinder", lang) in texts_of(at))

check("модель не вызвана ни разу", STATE["ai_calls"] == [])

# ================================================================ статика страницы
check("страница не импортирует слой модели", not re.search(r"services\s+import\s+ai\b|services\.ai\b", SRC))
# Пишет страница ровно одно — копию паспорта, через services/passport_copies.py
# и только после проверки права в момент нажатия (tests/test_passport_copies.py).
check("страница сама SQL не пишет и в Amazon не ходит", not re.search(r"\bINSERT\b|\bUPDATE\b|spapi", SRC))
check("единственная запись — register() паспорта под ls.textgen.accept",
      SRC.count("pc.register(") == 1 and SRC.count("get_conn()") == 1
      and SRC.index('auth.require("ls.textgen.accept"') < SRC.index("get_conn()") < SRC.index("pc.register("))
check("страница не держит своей логики правил",
      "tr.check(" in SRC and not re.search(r"\bre\.(search|match|finditer|sub)\b", SRC))
check("компилируется (не только разбирается)", compile(SRC, str(PAGE), "exec") is not None)

# ================================================================ i18n
langs = i18n.LANGS
keys_in_src = set(re.findall(r't\("((?:tg|nav)\.[a-z_.]+)"', SRC))
dynamic = ({f"tg.field.{f}" for f in ps.FIELDS}
           | {f"tg.type.{k}" for k in ps.TYPE_BY_KEY}
           | {f"tg.code.{c}" for c in re.findall(r'add\("([A-Z_]+)"',
                                                (ROOT / "services" / "title_rules.py").read_text(encoding="utf-8"))}
           | {f"tg.src.{s}" for s in ("attribute", "snapshot", "highlights", "title", "kit")}
           | {f"tg.tier.{x}" for x in seo.TIERS}
           | {"tg.where.title", "tg.where.highlights", "auth.role.textgen_pilot"})
need = keys_in_src | dynamic
for lang in ("ru", "uk", "en"):
    miss = sorted(k for k in need if k not in langs[lang])
    check(f"{lang}: все ключи страницы на месте" + (f" — нет {miss}" if miss else ""), not miss)
check("коды правил собраны (не пустой набор)", len([k for k in dynamic if k.startswith("tg.code.")]) >= 16)
check("в источниках Spec нет незнакомых",
      set(re.findall(r'Spec\([^,]+,\s*"([a-z]+)"\)', (ROOT / "services" / "product_specs.py").read_text(encoding="utf-8")))
      <= {"attribute", "kit"})

# ================================================================ SQL для базы Кабинета
SQL_PATH = ROOT / "migrations" / "kabinet" / "2026-10-21_ls_textgen_role.sql"
check("SQL роли лежит в migrations/kabinet/", SQL_PATH.exists())
SQL = SQL_PATH.read_text(encoding="utf-8") if SQL_PATH.exists() else ""
code_sql = "\n".join(line.split("--")[0] for line in SQL.splitlines())
check("и не попадает в миграции listing_data (glob *.sql корня)",
      SQL_PATH.name not in {p.name for p in (ROOT / "migrations").glob("*.sql")})
check("одна транзакция", code_sql.strip().startswith("BEGIN;") and code_sql.strip().endswith("COMMIT;"))

ls_role_check = re.search(r"app_users_ls_role_check\s+CHECK\s*\((.*?)\);", code_sql, re.S)
perm_check = re.search(r"app_permissions_role_check\s+CHECK\s*\((.*?)\);", code_sql, re.S)


def arr(s):
    return set(re.findall(r"'([a-z_]+)'", s))


check("CHECK app_users: все роли кода, включая пилота",
      bool(ls_role_check) and arr(ls_role_check.group(1)) == set(auth.ROLES))
ls_branch = re.search(r"WHEN action LIKE 'ls\.%'\s*THEN role = ANY \(ARRAY\[(.*?)\]\)", code_sql, re.S)
check("CHECK app_permissions: ветка ls.* знает все роли кода",
      bool(perm_check and ls_branch) and arr(ls_branch.group(1)) == set(auth.ROLES))
check("ветка Кабинета не тронута",
      "ELSE role = ANY (ARRAY['viewer','country_manager','demand_planner','admin'])" in code_sql)
page_ins = re.search(r"SELECT 'ls\.page\.textgen', r\.role, r\.role IN \(([^)]*)\)", code_sql)
check("ls.page.textgen разрешён ровно тем ролям, что в коде",
      bool(page_ins) and arr(page_ins.group(1)) == auth._MATRIX["ls.page.textgen"])
roles_list = re.search(r"'ls\.page\.textgen'.*?FROM \(VALUES (.*?)\) AS r\(role\)", code_sql, re.S)
check("строка ls.page.textgen заводится для каждой роли",
      bool(roles_list) and arr(roles_list.group(1)) == set(auth.ROLES))
closed = re.search(r"SELECT a\.action, 'textgen_pilot', false.*?FROM \(VALUES (.*?)\) AS a\(action\)",
                   code_sql, re.S)
closed_set = set(re.findall(r"'(ls\.[a-z_.]+)'", closed.group(1))) if closed else set()
check("всё прочее роли пилота закрыто явными строками — список совпадает с матрицей кода",
      closed_set == set(auth._MATRIX) - {"ls.page.textgen"})
check("права не перетираются (ON CONFLICT DO NOTHING у обеих вставок)",
      code_sql.count("ON CONFLICT (action, role) DO NOTHING") == 2)
check("почта не подставлена — блок отказывается выполняться",
      "почта text := 'ПОДСТАВИТЬ_ПОЧТУ_ЯРОСЛАВА'" in code_sql
      and re.search(r"IF почта = 'ПОДСТАВИТЬ_ПОЧТУ_ЯРОСЛАВА' THEN\s+RAISE EXCEPTION", code_sql))
check("назначение — ровно одной строке, иначе отказ", "IF n <> 1 THEN" in code_sql)
check("кабинетная роль не трогается", not re.search(r"SET\s+role\s*=", code_sql))
check("карточек не заводит", "INSERT INTO kabinet_data.app_users" not in code_sql)

# ================================================== загрузка паспорта: «заменить?»
# Поток вопроса на ЭКРАНЕ (проверка #164): ответ на прежний вопрос не может ответить
# на новый; вопрос привязан к файлу; без права кнопок нет. Загрузку файла AppTest не
# умеет — подменяется сам `st.file_uploader`, а `register()` ведёт сценарий.
import hashlib  # noqa: E402
import io  # noqa: E402
import zipfile  # noqa: E402

import streamlit as _st  # noqa: E402

from services import db as _db  # noqa: E402
from services import passport_copies as pc  # noqa: E402


def _docx(pid: str, ver: str = "1") -> bytes:
    rows = [("passport_id", pid), ("passport_version", ver), ("sku_id", "99601000-B"), ("state", "NOT_READY")]
    tbl = "<w:tbl>" + "".join(f"<w:tr><w:tc><w:p><w:r><w:t>{a}</w:t></w:r></w:p></w:tc>"
                              f"<w:tc><w:p><w:r><w:t>{b}</w:t></w:r></w:p></w:tc></w:tr>" for a, b in rows) + "</w:tbl>"
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                   f'wordprocessingml/2006/main"><w:body>{tbl}</w:body></w:document>')
    return b.getvalue()


class _Up:
    def __init__(self, data):
        self.data, self.name = data, "p.docx"

    def getvalue(self):
        return self.data


FLOW = {"file": _docx("PASS-99601000-B-002"), "calls": [], "script": []}
_st.file_uploader = lambda *a, **k: _Up(FLOW["file"])
pc.volume_store = lambda: object()
_db.get_conn = lambda: type("C", (), {"close": lambda self: None})()
pc.copies = lambda sku: (pd.DataFrame(), None)


def _register(data, name, *, actor, store, conn, replace=()):
    FLOW["calls"].append(tuple(replace))
    step = FLOW["script"].pop(0)
    if step[0] == "ask":
        raise pc.CopyError("OTHER_PASSPORT_ACTIVE", ", ".join(step[1]), step[1])
    return pc.Outcome("REGISTERED", "DOCX-PASS-99601000-B-002-v1", "/Volumes/x", {}, list(replace))


pc.register = _register
A, B = ("DOCX-PASS-99601000-B-001-v2",), ("DOCX-PASS-99601000-B-003-v1",)


def _rkey(ids):
    return "tg-pp-replace-" + hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()[:12]


def _keys(at):
    return {b.key for b in at.button}


FLOW["script"] = [("ask", A)]
at = run()
at.button(key="tg-pp-save").click().run()
check("паспорт: другой действующий — вопрос с id копии и версией, записи нет",
      not at.exception and FLOW["calls"] == [()] and any(A[0] in str(w.value) for w in at.warning)
      and _rkey(A) in _keys(at))
# пока человек думал, коллега заменил A на B: ответ про A получает НОВЫЙ вопрос про B
FLOW["script"] = [("ask", B), ("ok",)]
at.button(key=_rkey(A)).click().run()
check("ответ на прежний вопрос — новый вопрос про B, не замена B",
      not at.exception and FLOW["calls"] == [(), A] and any(B[0] in str(w.value) for w in at.warning)
      and not at.success)
check("кнопки прежнего вопроса больше нет — новый вопрос, новая кнопка",
      _rkey(A) not in _keys(at) and _rkey(B) in _keys(at))
at.button(key=_rkey(B)).click().run()
check("подтверждение B — замена ровно B, итог без висящего вопроса",
      not at.exception and FLOW["calls"] == [(), A, B] and at.success
      and not any("DOCX-PASS" in str(w.value) for w in at.warning))
# вопрос привязан к файлу: другой файл — вопроса нет
FLOW["script"], FLOW["calls"] = [("ask", A)], []
at = run()
at.button(key="tg-pp-save").click().run()
FLOW["file"] = _docx("PASS-99601000-B-004")
at.run()
check("сменили файл — вопрос снят", not any(A[0] in str(w.value) for w in at.warning) and _rkey(A) not in _keys(at))
# без права — кнопки выключены, а нажатие (в обход) отказано в момент записи
_can, _req = auth.can, auth.require
auth.can = lambda a: False
auth.require = lambda *a, **k: False
FLOW["calls"] = []
at = run()
check("без права «Сохранить» выключена", at.button(key="tg-pp-save").disabled)
auth.can, auth.require = _can, _req

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
