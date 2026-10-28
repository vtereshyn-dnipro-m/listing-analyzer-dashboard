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
    и роли пилота, остальное роли пилота закрыто явными строками, почта (в
    отдельном файле назначения) не
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

# Генерация по паспорту: по умолчанию сохранённых паспортов нет — блок молчит.
# Сценарии генерации подменяют это ниже.
from services import textgen as tg  # noqa: E402

GEN = {"copies": (pd.DataFrame(), None)}
tg.active_copies = lambda: GEN["copies"]
# Справочник SKU Кабинета: по умолчанию пуст (связь SKU ↔ ASIN — сценарии ниже).
from services import passport as _passport_svc  # noqa: E402

LINK = {"dir": pd.DataFrame(columns=["sku", "asins"])}
_passport_svc.sku_directory = lambda: (LINK["dir"], LINK.get("err"))

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
# Слой модели страница берёт ТОЛЬКО чтобы передать его генерации по нажатию:
# сама она модель не зовёт (решение владельца 21.10.2026 — «Сгенерировать»).
check("модель зовётся только через tg.generate по кнопке, под ls.textgen.accept",
      SRC.count("ai.generate_json") == 1 and "ai_call=ai.generate_json" in SRC
      and SRC.count("tg.generate(") == 1
      and SRC.index('auth.require("ls.textgen.accept", object_type="textgen"') < SRC.index("tg.generate("))
# Пишет страница ровно одно — копию паспорта, через services/passport_copies.py
# и только после проверки права в момент нажатия (tests/test_passport_copies.py).
check("страница сама SQL не пишет и в Amazon не ходит", not re.search(r"\bINSERT\b|\bUPDATE\b|spapi", SRC))
# Запись копии — в общем блоке загрузки (components/passport_upload.py, один для
# генератора и раздела «Паспорт SKU», решение владельца 28.10.2026).
UP = (ROOT / "components" / "passport_upload.py").read_text(encoding="utf-8")
check("единственная запись — register() паспорта под ls.textgen.accept, в общем блоке загрузки",
      SRC.count("pc.register(") == 0 and 'passport_upload.render("tg-pp", say)' in SRC
      and UP.count("pc.register(") == 1 and UP.count("get_conn()") == 1
      and UP.index('auth.require("ls.textgen.accept"') < UP.index("get_conn()") < UP.index("pc.register(")
      and not re.search(r"\bINSERT\b|\bUPDATE\b|spapi", UP))
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
_tail = code_sql.split("COMMIT;", 1)[1] if "COMMIT;" in code_sql else "x"
check("одна транзакция, после неё — только проверочный SELECT",
      code_sql.strip().startswith("BEGIN;") and code_sql.count("COMMIT;") == 1
      and all(x.strip().upper().startswith("SELECT") for x in _tail.split(";") if x.strip()))

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
check("всё прочее роли пилота закрыто явными строками — список совпадает с матрицей кода "
      "(кроме страницы и ls.textgen.accept: его заводит свой файл)",
      closed_set == set(auth._MATRIX) - {"ls.page.textgen", "ls.textgen.accept"})
check("права не перетираются (ON CONFLICT DO NOTHING у обеих вставок)",
      code_sql.count("ON CONFLICT (action, role) DO NOTHING") == 2)
check("SQL роли никому роль не назначает (решение владельца: позже Алексею)",
      "UPDATE kabinet_data.app_users" not in code_sql)
# Назначение — отдельный файл, с заготовкой почты, которая отказывается выполняться.
ASSIGN = ROOT / "migrations" / "kabinet" / "2026-10-21_ls_textgen_assign.sql"
check("SQL назначения лежит рядом", ASSIGN.exists())
asg = "\n".join(line.split("--")[0] for line in ASSIGN.read_text(encoding="utf-8").splitlines()) if ASSIGN.exists() else ""
check("почта не подставлена — блок отказывается выполняться",
      "почта text := 'ПОДСТАВИТЬ_ПОЧТУ'" in asg
      and re.search(r"IF почта = 'ПОДСТАВИТЬ_ПОЧТУ' THEN\s+RAISE EXCEPTION", asg))
check("назначение — ровно одной строке, иначе отказ", "IF n <> 1 THEN" in asg)
check("назначение — одна транзакция, после неё только SELECT",
      asg.strip().startswith("BEGIN;") and asg.count("COMMIT;") == 1
      and all(x.strip().upper().startswith("SELECT") for x in asg.split("COMMIT;", 1)[-1].split(";") if x.strip()))
check("назначается только роль пилота", re.findall(r"SET ls_role = '([a-z_]+)'", asg) == ["textgen_pilot"])
check("кабинетная роль не трогается", not re.search(r"SET\s+role\s*=", code_sql + asg))
check("карточек не заводит", "INSERT INTO kabinet_data.app_users" not in code_sql + asg)

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

# ======================================================= генерация по паспорту
# Кнопка «Сгенерировать» (решение владельца 21.10.2026): право ls.textgen.accept,
# лимиты — кнопка выключается с объяснением; модель зовётся только через
# tg.generate по нажатию. База, том и модель подменены.
_db.table_exists = lambda name: True
METHOD = {"text": "методология textgen", "ver": 1}


def _safe_read(sql, params=None):
    if "synthesis_skill" in sql:
        if not METHOD["text"]:
            return pd.DataFrame(), None
        return pd.DataFrame([{"skill_text": METHOD["text"], "version": METHOD["ver"]}]), None
    return pd.DataFrame(), None


_db.safe_read = _safe_read
GEN["copies"] = (pd.DataFrame([{"source_artifact_id": "DOCX-PASS-99601000-B-001-v2", "sku_id": "99601000-B",
                                "passport_id": "PASS-99601000-B-001", "sha256": "0" * 64,
                                "archived_locator": "/Volumes/dnipro_m/listing_data/passports/x.docx",
                                "recorded_at": "2026-10-21"}]), None)
GEN.update(usage=tg.Usage(), calls=[], latest=(pd.DataFrame(), None))
tg.usage_now = lambda sku: (GEN["usage"], None)
tg.latest = lambda sku, mp: GEN["latest"]


GEN["stamped"] = True
GEN["rules_version"] = "f" * 40
# Коммит подменён: без .git рядом (копия без репозитория) проверка сравнивала бы
# None с None и ничего не запирала (проверка #175).
import deploy_sync  # noqa: E402

FAKE_COMMIT = "f" * 40
deploy_sync.current_commit = lambda: FAKE_COMMIT


def _generate(**kw):
    GEN["calls"].append(kw)
    return tg.Result("OK", proposal_id="TG-7", cost_usd=0.031, stamped=GEN["stamped"],
                     rules_version=GEN["rules_version"] if GEN["stamped"] else None)


tg.generate = _generate
_task_config = ai.task_config
ai.task_config = lambda task: ("anthropic", "claude-sonnet-5")


def esc(x: str) -> str:
    return x.replace("$", "\\$")


def _warn(at):
    return "\n".join(str(w.value) for w in at.warning)


at = run()
btn = at.button(key="tg-gen-go")
check("генерация: кнопка есть и включена при методологии, цене и запасе лимита", not btn.disabled)
check("генерация: расход за сегодня назван у кнопки, «$» экранирован для markdown",
      esc(lab("tg.gen.usage", n=0, n_max=10, a=0.0, a_max=1.0, b=0.0, b_max=10.0)) in texts_of(at)
      and "\\$0.00 / \\$1 на товар · пилот \\$0.00 / \\$10" in texts_of(at))
check("лимиты в подсказке — словами владельца, «$» экранирован",
      "10 вызовов на товар в сутки, \\$1 на товар в сутки, \\$10 в сутки на пилот" in texts_of(at))
btn.click().run()
check("нажатие — ровно один вызов генерации, модель — слой ai, автор и рынок переданы",
      len(GEN["calls"]) == 1 and GEN["calls"][0]["ai_call"] is ai.generate_json
      and GEN["calls"][0]["sku"] == "99601000-B" and GEN["calls"][0]["marketplace"] == "es"
      and GEN["calls"][0]["method"] == ("методология textgen", 1))
check("итог генерации назван", any("TG-7" in str(x.value) for x in at.success))
check("на всей странице нет неэкранированного «$» в тексте сообщений",
      not any(re.search(r"(?<!\\)\$", str(e.value))
              for coll in (at.caption, at.warning, at.success, at.info, at.error) for e in coll))
check("настоящая модель при этом не вызывалась", STATE["ai_calls"] == [])
check("штамп: в генерацию передан коммит кода правил (deploy_sync)",
      GEN["calls"][0].get("rules_version") == FAKE_COMMIT)
check("штамп записан — подписи про миграцию нет", tg.STAMP_MIGRATION not in texts_of(at))
GEN["stamped"] = False
at = run()
at.button(key="tg-gen-go").click().run()
check("штамп не записан (нет миграции) — сказано и назван файл",
      lab("tg.gen.no_stamp", file=tg.STAMP_MIGRATION) in texts_of(at) and any("TG-7" in str(x.value) for x in at.success))
GEN["stamped"] = True
GEN["rules_version"] = None
at = run()
at.button(key="tg-gen-go").click().run()
check("штамп записан, а коммит не прочитан — сказано, что версия правил пустая",
      lab("tg.gen.no_rules_version") in texts_of(at) and tg.STAMP_MIGRATION not in texts_of(at))
GEN["rules_version"] = "f" * 40
at = run()
at.button(key="tg-gen-go").click().run()
check("штамп и версия записаны — ни одной подписи про штамп",
      lab("tg.gen.no_rules_version") not in texts_of(at) and tg.STAMP_MIGRATION not in texts_of(at))

GEN["usage"] = tg.Usage(calls_sku=10)
at = run()
check("лимит 10 вызовов на товар — кнопка выключена и сказано почему",
      at.button(key="tg-gen-go").disabled and lab("tg.gen.err.LIMIT_CALLS", detail="10/10") in _warn(at))
GEN["usage"] = tg.Usage(usd_pilot=9.99)
at = run()
check("лимит $10 на пилот (с оценкой следующего вызова) — кнопка выключена",
      at.button(key="tg-gen-go").disabled and "\\$10" in _warn(at))
GEN["usage"] = tg.Usage()
METHOD["text"] = ""
_st.cache_data.clear()       # методология кэшируется страницей на 120 с
at = run()
check("методологии textgen нет — кнопка выключена и названо, где заполнить",
      at.button(key="tg-gen-go").disabled and lab("tg.gen.err.NO_METHOD", detail="textgen") in _warn(at))
METHOD["text"] = "методология textgen"
_st.cache_data.clear()
ai.task_config = lambda task: ("anthropic", "model-without-price")
at = run()
check("цена модели неизвестна — кнопка выключена",
      at.button(key="tg-gen-go").disabled and "model-without-price" in _warn(at))
ai.task_config = lambda task: ("anthropic", "claude-sonnet-5")
_db.table_exists = lambda name: False
at = run()
check("нет журнала генерации — кнопка выключена и названа миграция",
      at.button(key="tg-gen-go").disabled and "2026-10-21_textgen_calls.sql" in _warn(at))
_db.table_exists = lambda name: name != "content_versions"
at = run()
check("нет таблицы черновиков — кнопка выключена", at.button(key="tg-gen-go").disabled
      and "content_versions" in _warn(at))
_db.table_exists = lambda name: True
ai.task_config = lambda task: ("gemini", "gemini-3.5-flash")
at = run()
check("не Anthropic — кнопка выключена и сказано почему", at.button(key="tg-gen-go").disabled
      and "gemini" in _warn(at))
ai.task_config = lambda task: ("anthropic", "claude-sonnet-5")
_can = auth.can
auth.can = lambda a: a != "ls.textgen.accept"
at = run()
check("без права ls.textgen.accept «Сгенерировать» выключена", at.button(key="tg-gen-go").disabled)
auth.can = _can

# Связь SKU ↔ ASIN: справочник Кабинета по точному коду, матрица ES вторым источником.
MATRIX_ES = pd.DataFrame([{"asin": "B0H75P364R", "sku_group": "S5_78739000"},
                          {"asin": "B0GTRY26HB", "sku_group": "99601000"}])


LINK["mx_err"] = None
LINK["de_err"] = None
MATRIX_DE = pd.DataFrame([{"asin": "B0DEDEDEDE", "sku_group": "99601000-B"}])


def _safe_read2(sql, params=None):
    if "product_matrix" in sql:
        # площадка — из САМОГО запроса: подставлена параметром или вписана литералом
        lit = re.search(r"marketplace = '([a-z.]+)'", sql)
        mp = (params or {}).get("mp") if "%(mp)s" in sql else (lit.group(1) if lit else None)
        if mp == "de":
            return (pd.DataFrame(), LINK["de_err"]) if LINK["de_err"] else (MATRIX_DE, None)
        if LINK["mx_err"]:
            return pd.DataFrame(), LINK["mx_err"]
        return MATRIX_ES, None
    return _safe_read(sql, params)


_db.safe_read = _safe_read2
_st.cache_data.clear()
LINK["dir"] = pd.DataFrame([{"sku": "99601000-B", "asins": "B0GTRY26HB"}])
at = run()
check("сверху у ASIN назван его SKU (матрица)", lab("tg.link.sku", skus="S5_78739000") in texts_of(at))
check("внизу у SKU генерации — его ASIN ES (справочник по точному коду)",
      lab("tg.link.asins", asins="B0GTRY26HB") in texts_of(at))
GEN["calls"].clear()
at.button(key="tg-gen-go").click().run()
check("генерация получает ASIN товара на выбранной площадке",
      GEN["calls"] and GEN["calls"][-1]["asins"] == ["B0GTRY26HB"])
# Площадка DE: свой ASIN из матрицы DE, а не ES (у товара они разные).
LINK["dir"] = pd.DataFrame([{"sku": "99601000-B", "asins": "B0GTRY26HB B0DEDEDEDE"}])
_st.cache_data.clear()
at = run()
at.selectbox(key="tg-gen-mp").set_value("de").run()
check("DE: до нажатия видно, какой ASIN уйдёт в черновики",
      lab("tg.link.draft_asin", mp="DE", asin="B0DEDEDEDE") in texts_of(at))
check("подпись до нажатия решает тот же pick_asin, что и запись",
      "g_pick, g_why = tg.pick_asin(g_link_asins)" in SRC)
GEN["calls"].clear()
at.button(key="tg-gen-go").click().run()
check("DE: генерация получает ASIN площадки DE, а не ES",
      GEN["calls"] and GEN["calls"][-1]["asins"] == ["B0DEDEDEDE"] and GEN["calls"][-1]["marketplace"] == "de")
LINK["de_err"] = "OperationalError: de down"
_st.cache_data.clear()
at = run()
at.selectbox(key="tg-gen-mp").set_value("de").run()
GEN["calls"].clear()
at.button(key="tg-gen-go").click().run()
check("DE: матрица не прочитана — сбой назван, в генерацию «не прочитано» (None), не «ASIN нет»",
      "de down" in texts_of(at) and GEN["calls"] and GEN["calls"][-1]["asins"] is None)
LINK["de_err"] = None
LINK["dir"] = pd.DataFrame([{"sku": "99601000-B", "asins": "B0GTRY26HB"}])
_st.cache_data.clear()
at = run()
check("ASIN сверху не этот товар — предупреждение о разных товарах",
      lab("tg.link.mismatch", asin="B0H75P364R", sku="99601000-B", asins="B0GTRY26HB", top="S5_78739000") in _warn(at))
LINK["dir"] = pd.DataFrame([{"sku": "99601000-B", "asins": "B0H75P364R"}])
_st.cache_data.clear()
at = run()
check("совпали — предупреждения о разных товарах нет",
      lab("tg.link.asins", asins="B0H75P364R") in texts_of(at)
      and lab("tg.link.mismatch", asin="B0H75P364R", sku="99601000-B", asins="B0H75P364R", top="S5_78739000, 99601000-B")
      not in _warn(at) and "tg.link.mismatch" not in _warn(at)
      and not any(i18n.LANGS["ru"]["tg.link.mismatch"].split("{")[0] in str(w.value) for w in at.warning))
LINK["dir"] = pd.DataFrame(columns=["sku", "asins"])
_st.cache_data.clear()
at = run()
check("у SKU нет ASIN ES — сказано, а не молчание",
      lab("tg.link.asins_none", sku="99601000-B") in texts_of(at)
      and lab("tg.link.no_asin", sku="99601000-B", asin="B0H75P364R") in _warn(at))
check("вариант 99601000-B не сопоставляется с базовым 99601000 матрицы по догадке",
      tg.asins_for_sku("99601000-B", None, MATRIX_ES) == [])

# Сбой источника — «не прочитано», а не «не найдено» (проверка #168).
LINK["dir"], LINK["err"] = pd.DataFrame(columns=["sku", "asins"]), "OperationalError: kabinet down"
_st.cache_data.clear()
at = run()
check("справочник не прочитан — сказано у генерации, а не «ASIN ES не найден» с предупреждением",
      "kabinet down" in texts_of(at) and lab("tg.link.unread", sku="99601000-B") in texts_of(at)
      and lab("tg.link.asins_none", sku="99601000-B") not in texts_of(at)
      and lab("tg.link.no_asin", sku="99601000-B", asin="B0H75P364R") not in _warn(at))
check("справочник не прочитан — матрица всё равно даёт SKU сверху", lab("tg.link.sku", skus="S5_78739000") in texts_of(at))
GEN["calls"].clear()
at.button(key="tg-gen-go").click().run()
check("связь не прочитана — генерации уходит «не прочитано» (None), а не неполный список",
      GEN["calls"] and GEN["calls"][-1]["asins"] is None)
check("подпись о сбое — и сверху, и у генерации (две)",
      sum(1 for c in at.caption if "kabinet down" in str(c.value)) == 2)
LINK["err"], LINK["mx_err"] = None, "OperationalError: matrix down"
LINK["dir"] = pd.DataFrame([{"sku": "99601000-B", "asins": "B0GTRY26HB B0DEDEDEDE"}])
_st.cache_data.clear()
at = run()
check("матрица не прочитана — ASIN справочника не выдаются за ES и «не найдено» не пишется",
      "matrix down" in texts_of(at) and "B0DEDEDEDE" not in texts_of(at)
      and lab("tg.link.sku_none") not in texts_of(at) and lab("tg.link.unread", sku="99601000-B") in texts_of(at))
LINK["mx_err"] = None
check("ASIN справочника с другого рынка не выдаётся за ES",
      tg.asins_for_sku("99601000-B", LINK["dir"], MATRIX_ES) == ["B0GTRY26HB"])
check("без матрицы ES не проверить — ответ пустой", tg.asins_for_sku("99601000-B", LINK["dir"], None) == [])
NAN_DIR = pd.DataFrame([{"sku": "99601000-B", "asins": float("nan")}, {"sku": float("nan"), "asins": "B0GTRY26HB"}])
check("NaN в ячейке справочника — не «nan» (правило 4)",
      "nan" not in tg.asins_for_sku("99601000-B", NAN_DIR, MATRIX_ES)
      and "nan" not in tg.skus_for_asin("B0GTRY26HB", NAN_DIR, MATRIX_ES))
check("конкуренты в связь не идут (запрос матрицы)", "is_competitor IS NOT TRUE" in SRC)
# «$» внутри `кода` не экранируется: там обратная косая осталась бы на экране.
_st.cache_data.clear()
at = run(title="DNIPRO-M Amoladora $ 125mm")
check("запрещённый «$» в тайтле назван как `$`, без обратной косой",
      any("`$`" in str(m.value) for m in at.markdown) and not any("`\\$`" in str(m.value) for m in at.markdown))
LINK["dir"] = pd.DataFrame(columns=["sku", "asins"])
_db.safe_read = _safe_read

GEN["latest"] = (pd.DataFrame([
    {"field": f, "text": f"текст {f}", "text_len": 10, "version": 1, "proposal_id": "TG-7", "status": "draft",
     "model": "claude-sonnet-5", "created_at": "2026-10-21 22:00",
     "checks": ('[{"code": "BRAND_NOT_FIRST", "field": "title", "detail": "DNIPRO-M"}]' if f == "title" else "[]")}
    for f in tg.FIELDS]), None)
at = run()
full = texts_of(at)
check("последнее предложение показано целиком — 8 полей",
      len([c for c in at.code if str(c.value).startswith("текст ")]) == 8)
check("нарушение правил тайтла из checks названо", lab("tg.code.BRAND_NOT_FIRST") in full)
GEN["latest"] = (GEN["latest"][0].assign(checks="[]"), None)
at = run()
check("без нарушений — так и сказано", lab("tg.gen.ok_checks") in texts_of(at))
_lat = GEN["latest"][0].copy()
_lat["asin"] = None
_lat.loc[_lat["field"] == "title", "checks"] = '[{"code": "ASIN_AMBIGUOUS", "field": "title", "detail": "B0A, B0B"}]'
GEN["latest"] = (_lat, None)
at = run()
check("пометка про ASIN — не нарушение: «нарушений нет» и отдельная строка с причиной",
      lab("tg.gen.ok_checks") in texts_of(at)
      and lab("tg.link.saved_no_asin", why=lab("tg.code.ASIN_AMBIGUOUS") + " (B0A, B0B)") in texts_of(at))
GEN["latest"] = (_lat.assign(checks="[]"), None)
at = run()
check("старые черновики без пометки — «причина не записана», а не прочерк",
      lab("tg.link.saved_no_asin", why=lab("tg.link.saved_no_reason")) in texts_of(at))
GEN["latest"] = (_lat.assign(asin="B0GTRY26HB", checks="[]"), None)
at = run()
check("сохранённый ASIN черновиков показан", lab("tg.link.saved_asin", asin="B0GTRY26HB") in texts_of(at))
# --- генератор на том же SKU, что выбран в разделе «Паспорт SKU», и тип товара в
# генерацию (поручение владельца 28.10.2026: выпадающий список товаров)
import services.passport as _pp_svc  # noqa: E402

GEN["copies"] = (pd.DataFrame([dict(GEN["copies"][0].iloc[0]),
                               {"source_artifact_id": "DOCX-PASS-21680000-001-v1", "sku_id": "21680000",
                                "passport_id": "PASS-21680000-001", "sha256": "1" * 64,
                                "archived_locator": "/Volumes/dnipro_m/listing_data/passports/y.docx",
                                "recorded_at": "2026-10-28"}]), None)
_sku_type = _pp_svc.sku_type
_pp_svc.sku_type = lambda sku: ({"21680000": "battery"}.get(sku), None)
at = AppTest.from_file(str(PAGE), default_timeout=60)
at.session_state["lang"] = "ru"
at.session_state["pp-sku"] = "21680000"
at.run()
check("генератор встаёт на SKU, выбранный в разделе «Паспорт SKU»", at.selectbox(key="tg-gen-sku").value == "21680000")
check("тип товара из листинга назван у генерации", lab("tg.gen.type", type=lab("tg.type.battery")) in texts_of(at))
GEN["calls"].clear()
at.button(key="tg-gen-go").click().run()
check("тип товара уходит в генерацию — по нему правила (аккумулятор: вольтаж в тайтле можно)",
      GEN["calls"] and GEN["calls"][-1].get("tool_type") == "battery")
at.selectbox(key="tg-gen-sku").set_value("99601000-B").run()
check("в генераторе можно выбрать другой SKU, контекст его не перебивает",
      at.selectbox(key="tg-gen-sku").value == "99601000-B" and lab("tg.gen.type_unknown") in texts_of(at))
at.session_state["pp-sku"] = "21680000"
at.run()
check("контекст не менялся — выбор в генераторе держится", at.selectbox(key="tg-gen-sku").value == "99601000-B")
_pp_svc.sku_type = _sku_type
ai.task_config = _task_config

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
