# -*- coding: utf-8 -*-
"""
tests/test_textgen_page.py — «Генератор текстов (пилот)»: логическая страница
(ТЗ владельца 29.10.2026, блоки 1, 3 и 5).

Проверяется то, что ломается тихо:

  · товар — ОДИН выбор на всю страницу (список Реестра, как в «Паспорт SKU»):
    верхнего выбора ASIN и второго выбора SKU у генерации нет; выбор общий с
    «Паспорт SKU» и Верификатором (pp-sku) в обе стороны; поиск по SKU, названию,
    модели, ASIN и EAN;
  · площадка и язык — ES подписью, не выбираются;
  · ASIN ES — только если он ровно один, иначе пусто с причиной («нет ASIN ES»,
    «ASIN неоднозначен, не выбран», связь не прочитана);
  · характеристик листинга на странице нет;
  · ручная проверка и ключи — свёрнуты внизу, с подписями «в генерацию не идёт» и
    «факты паспорта здесь не проверяются»; нарушения на экране — ровно те, что
    вернул `title_rules.check()` с типом из `passport.sku_type` и моделью из
    паспорта; без паспорта префикс «Model …: » назван непроверенным;
  · без паспорта блок генерации на месте, кнопка выключена с причиной; модель и
    методология названы до нажатия;
  · сбой чтения — ошибка с причиной, а не пустота; модель не вызывается вовсе;
  · колонки таблиц — технические имена (правило 3), подписи из `t()`;
  · SQL роли для базы Кабинета — как раньше.

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
    if asin not in PILOT:
        return {"title": "", "attributes": {}, "amazon_type": None, "product_information": {},
                "item_highlight": ""}, None
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
    STATE["keys_title"] = title
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

GEN = {"copies": (pd.DataFrame(), None), "usage": tg.Usage(), "calls": [], "latest": (pd.DataFrame(), None)}
tg.active_copies = lambda: GEN["copies"]
# учёт лимитов и последнее предложение — из журнала; подменены с самого начала: блок
# генерации теперь виден у любого выбранного товара (решение владельца 29.10.2026)
tg.usage_now = lambda sku: (GEN["usage"], None)
tg.latest = lambda sku, mp: GEN["latest"]
# Справочник SKU Кабинета: по умолчанию пуст (связь SKU ↔ ASIN — сценарии ниже).
from services import passport as _passport_svc  # noqa: E402

LINK = {"dir": pd.DataFrame(columns=["sku", "asins"])}
_passport_svc.sku_directory = lambda: (LINK["dir"], LINK.get("err"))

# Справочник SKU Кабинета, матрица ES, тип товара и паспорта — для блока 1 и блока 5.
DIR = pd.DataFrame([
    {"sku": "SKU-GRIND", "name": "Amoladora DGA-201M", "ean": "4820000000011", "asins": "B0H75P364R"},
    {"sku": "SKU-CORDED", "name": "Amoladora con cable", "ean": "", "asins": "B0FZFCQN3H"},
    {"sku": "SKU-TWO", "name": "Dos ASIN", "ean": "", "asins": "B0H75P364R B0FZFCQN3H"},
    {"sku": "SKU-NONE", "name": "Sin ASIN", "ean": "", "asins": ""},
    {"sku": "99601000-B", "name": "Пилосос DVB-200BC Dual", "ean": "", "asins": "B0GTRY26HB"},
    {"sku": "21680000", "name": "Насос PW-14B", "ean": "", "asins": ""},
])
LINK["dir"] = DIR
MX = {"es": pd.DataFrame([{"asin": "B0H75P364R", "sku_group": "x"}, {"asin": "B0FZFCQN3H", "sku_group": "y"},
                          {"asin": "B0GTRY26HB", "sku_group": "99601000"}]), "err": None}
METHOD = {"text": "методология textgen", "ver": 1}

from services import db as _db  # noqa: E402


def _fake_read(sql, params=None):
    if "synthesis_skill" in sql:
        if not METHOD["text"]:
            return pd.DataFrame(), None
        return pd.DataFrame([{"skill_text": METHOD["text"], "version": METHOD["ver"]}]), None
    if "product_matrix" in sql:
        return (pd.DataFrame(), MX["err"]) if MX["err"] else (MX["es"], None)
    return pd.DataFrame(), None


_db.safe_read = _fake_read
TYPES = {"SKU-GRIND": "grinder", "SKU-CORDED": "grinder", "SKU-TWO": "grinder", "21680000": "battery",
         "99601000-B": "blower"}
TYPE_ERR = {"err": None}
_passport_svc.sku_type = lambda sku: (None, TYPE_ERR["err"]) if TYPE_ERR["err"] else (TYPES.get(sku), None)

import hashlib  # noqa: E402
import io  # noqa: E402
import zipfile  # noqa: E402

from services import passport_copies as pc  # noqa: E402


def _pcell(text):
    return f"<w:tc><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"


def passport_docx(sku: str, model: str) -> bytes:
    """Копия паспорта: шапка и раздел идентичности с моделью — модель для префикса."""
    def tbl(rows):
        return "<w:tbl>" + "".join("<w:tr>" + "".join(_pcell(c) for c in r) + "</w:tr>" for r in rows) + "</w:tbl>"
    head = '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Ідентичність товару</w:t></w:r></w:p>'
    body = (tbl([("Параметр", "Значення"), ("passport_id", f"PASS-{sku}-001"), ("passport_version", "1"),
                 ("state", "NOT_READY"), ("sku_id", sku)])
            + head + tbl([("Поле", "Значення", "Статус", "Джерело"), ("Модель", model, "PROPOSED", "SRC-1")]))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                   f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    return b.getvalue()


GRIND_DOCX = passport_docx("SKU-GRIND", "DGA-201M")
DOCS = {"/Volumes/x/grind.docx": GRIND_DOCX}
pc.volume_store = lambda: type("S", (), {"get": lambda self, loc: DOCS[loc]})()
GEN["copies"] = (pd.DataFrame([{"source_artifact_id": "DOCX-PASS-SKU-GRIND-001-v1", "sku_id": "SKU-GRIND",
                                "passport_id": "PASS-SKU-GRIND-001", "sha256": hashlib.sha256(GRIND_DOCX).hexdigest(),
                                "archived_locator": "/Volumes/x/grind.docx", "recorded_at": "2026-10-29"}]), None)

from streamlit.testing.v1 import AppTest  # noqa: E402

from components.ui import eyebrow  # noqa: E402


def run(sku="99601000-B", title=None, hl=None, lang="ru", **state):
    """Прогон страницы с выбранным товаром (pp-sku — общий выбор с «Паспорт SKU»)."""
    at = AppTest.from_file(str(PAGE), default_timeout=60)
    at.session_state["lang"] = lang
    if sku:
        at.session_state["pp-sku"] = sku
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    if title is not None:
        at.text_input(key=f"tg-title-{sku}").input(title)
    if hl is not None:
        at.text_area(key=f"tg-hl-{sku}").input(hl)
    if title is not None or hl is not None:
        at.run()
    return at


def _warn(at):
    return "\n".join(str(w.value) for w in at.warning)


def block5(at):
    return next((e for e in at.expander if e.label == lab("tg.b5.title")), None)


def picker(at):
    return [s for s in at.selectbox if str(s.key).startswith("pp-pick-")]


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


# ================================================================ блок 1: один выбор
at = run(sku="SKU-GRIND")
check("страница открывается без исключения", not at.exception)
full = texts_of(at)
check("ни одного сырого ключа на экране", not re.search(r"\btg\.[a-z_]+(\.[A-Za-z_]+)?\b", full))
keys = {str(w.key) for coll in (at.selectbox, at.text_input, at.text_area, at.multiselect) for w in coll}
check("верхнего выбора ASIN и второго выбора SKU и площадки у генерации нет",
      not keys & {"tg-asin", "tg-gen-sku", "tg-gen-mp"})
check("выбор товара — один на страницу, он и есть общий выбор pp-sku",
      len(picker(at)) == 1 and picker(at)[0].value == "SKU-GRIND")
check("площадка и язык — ES подписью", lab("tg.b1.mp_lang") in full)
check("тип товара — из данных товара (passport.sku_type), назван под выбором",
      lab("tg.gen.type", type=lab("tg.type.grinder")) in full)
check("ASIN ES ровно один — назван", lab("tg.b1.asin", asin="B0H75P364R") in full)
check("характеристик листинга нет: ни таблицы «поле · значение · источник», ни метрик, ни раздела",
      not any(list(getattr(d.value, "columns", [])) == ["field", "value", "src"] for d in at.dataframe)
      and not at.metric and lab("tg.for_title") not in full
      and not any(str(m.value) in (eyebrow(lab("tg.product")), eyebrow(lab("tg.specs"))) for m in at.markdown))
b5 = block5(at)
check("ручная проверка и ключи — свёрнуты внизу, с подписями «в генерацию не идёт» и «факты паспорта не проверяются»",
      b5 is not None and b5.proto.expanded is False and lab("tg.b5.hint") in full and lab("tg.b5.keys_hint") in full
      and any(str(w.key) == "tg-title-SKU-GRIND" for w in b5.text_input))
check("модель и методология названы до нажатия «Сгенерировать»",
      any(str(c.value).startswith(lab("tg.gen.model_method", model="§", ver=0).split("§")[0]) for c in at.caption))
check("ключи по типу: число наших товаров названо", lab("tg.keys_from", n=3) in full)
check("до ввода текста нарушений не показано", not at.success
      and not any(lab("tg.violations", n=1).split("1")[0] in str(e.value) for e in at.error))

print("ASIN ES — только если он ровно один")
at = run(sku="SKU-TWO")
check("два ASIN — пусто, «ASIN неоднозначен, не выбран» с обоими",
      lab("tg.b1.asin_none", why=lab("tg.b1.why.ASIN_AMBIGUOUS") + " (B0FZFCQN3H, B0H75P364R)") in texts_of(at))
at = run(sku="SKU-NONE")
check("ни одного — пусто, «нет ASIN ES»", lab("tg.b1.asin_none", why=lab("tg.b1.why.ASIN_UNKNOWN")) in texts_of(at))
MX["err"] = "OperationalError: matrix down"
_st_mod = __import__("streamlit")
_st_mod.cache_data.clear()
at = run(sku="SKU-GRIND")
check("связь не прочитана — пусто с причиной, сбой назван, а не «нет ASIN ES»",
      lab("tg.b1.asin_none", why=lab("tg.b1.why.ASIN_UNREAD")) in texts_of(at) and "matrix down" in texts_of(at)
      and lab("tg.b1.why.ASIN_UNKNOWN") not in texts_of(at))
MX["err"] = None
_st_mod.cache_data.clear()

print("поиск по SKU, названию, модели, ASIN и EAN")
at = run(sku="SKU-GRIND", **{"tg-q": "B0FZFCQN3H"})
opts = [o.split(" · ")[0] for o in picker(at)[0].options if o != lab("pp.pick.none")]
check("поиск по ASIN — в списке только товары с этим ASIN", sorted(opts) == ["SKU-CORDED", "SKU-TWO"])
check("найдено и в списке — названо", lab("tg.b1.found", n=2, shown=2) in texts_of(at))
check("выбранный товар вне поиска — выбор не меняется и сказано об этом",
      at.session_state["pp-sku"] == "SKU-GRIND" and lab("pp.pick.ctx_outside_q", sku="SKU-GRIND") in texts_of(at))
at = run(sku="SKU-NONE", **{"tg-q": "4820000000011"})
check("поиск по EAN", [o.split(" · ")[0] for o in picker(at)[0].options if o != lab("pp.pick.none")] == ["SKU-GRIND"])

print("общий выбор в обе стороны")
at = run(sku="SKU-GRIND")
g0 = at.session_state["pp-sku-gen"] if "pp-sku-gen" in at.session_state else 0
picker(at)[0].set_value("SKU-CORDED").run()
check("выбор в генераторе пишет общий выбор pp-sku (его видят «Паспорт SKU» и Верификатор)",
      at.session_state["pp-sku"] == "SKU-CORDED" and at.session_state["pp-sku-gen"] == g0 + 1)
check("и страница сразу на новом товаре: свой ASIN ES, свой ключ ручной проверки",
      lab("tg.b1.asin", asin="B0FZFCQN3H") in texts_of(at)
      and any(str(w.key) == "tg-title-SKU-CORDED" for w in block5(at).text_input))
check("своего выбора у генератора нет — tg-gen-choice не появляется", "tg-gen-choice" not in at.session_state)

print("без паспорта")
check("товар без паспорта: блок генерации на месте, кнопка выключена с причиной «Паспорт отсутствует»",
      at.button(key="tg-gen-go").disabled and lab("tg.gen.title") in texts_of(at)
      and lab("tg.gen.err.NO_PASSPORT", detail="") in _warn(at)
      and lab("tg.gen.err.NO_PASSPORT", detail="").startswith("Паспорт отсутствует"))
at = run(sku="", lang="ru")
check("товар не выбран — подсказка выбрать, ниже ничего не считается",
      not at.exception and lab("tg.b1.pick_first") in texts_of(at) and block5(at) is None)

# ================================================================ блок 5: ручная проверка
cases = [
    ("инструмент: вольтаж и «!» в тайтле, бренд не первым",
     "Amoladora Dnipro-M DGA-201M 20V, 10000rpm!", ""),
    ("единица через пробел и бренд не в том регистре",
     "Dnipro-M DGA-201M Amoladora Angular, 125 mm", ""),
    ("Highlights без префикса модели", "DNIPRO-M DGA-201M Amoladora Angular, Ø125mm",
     "Velocidad 10000rpm"),
]
for name, title, hl in cases:
    at = run(sku="SKU-GRIND", title=title, hl=hl)
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
at = run(sku="SKU-GRIND", title=ok_title, hl=ok_hl)
check("чистый текст — «нарушений нет»; модель для префикса — из паспорта (DGA-201M)",
      any(lab("tg.all_ok") == str(x.value) for x in at.success)
      and not any(lab("tg.no_model_prefix") == str(w.value) for w in at.warning))
check("вольтаж в Highlights у инструмента — не нарушение", not bullets(at))
at = run(sku="SKU-GRIND", hl="Model DGB-999X: compatible")
check("префикс с чужой моделью — нарушение: модель берётся из паспорта, а не из текста",
      tr.check("", "Model DGB-999X: compatible", kind=tr.TOOL, model="DGA-201M") != [] and bullets(at))
at = run(sku="SKU-GRIND", title="DNIPRO-M DGA-201M Amoladora Angular 20V, Ø125mm")
check("тот же вольтаж в тайтле — нарушение TOOL_VOLTAGE с полем «тайтл»",
      any(lab("tg.code.TOOL_VOLTAGE") in b and lab("tg.where.title") in b for b in bullets(at)))
at = run(sku="21680000", title="DNIPRO-M Batería BP-240 20V 4Ah")
check("тип из выбранного SKU: аккумулятор — вольтаж в тайтле не нарушение (passport.sku_type)",
      not any(lab("tg.code.TOOL_VOLTAGE") in b for b in bullets(at)))
at = run(sku="SKU-GRIND", title="x" * 80)
check("счётчик длины: 80 / 75 акцентом",
      any("80 / 75" in str(m.value) and "#E8590C" in str(m.value) for m in at.markdown))
at = run(sku="SKU-CORDED", title="DNIPRO-M Amoladora Angular, Ø125mm", hl="Velocidad 10000rpm")
check("паспорта нет — модели нет: префикс Highlights назван непроверенным",
      any(lab("tg.no_model_prefix") == str(w.value) for w in at.warning))
at = run(sku="SKU-CORDED", title="DNIPRO-M Amoladora Angular, Ø125mm")
check("и без Highlights оговорки нет", not any(lab("tg.no_model_prefix") == str(w.value) for w in at.warning))

# ключи: отметка «есть в тексте» по введённому; нынешний тайтл — из снапшота ASIN ES
at = run(sku="SKU-GRIND", title="DNIPRO-M DGA-201M Amoladora Angular, Ø125mm")
kdf = next(d.value for d in at.dataframe if "query" in getattr(d.value, "columns", []))
check("колонки ключей — технические имена",
      list(kdf.columns) == ["query", "volume", "tier", "asins", "typed"])
check("введённый ключ отмечен, невведённый — нет",
      bool(kdf.set_index("query").loc["amoladora angular", "typed"])
      and not bool(kdf.set_index("query").loc["radial bosch", "typed"]))
check("чужой бренд — «не брать»",
      kdf.set_index("query").loc["radial bosch", "tier"] == lab("tg.tier.forbid"))
_st_mod.cache_data.clear()          # ключи кэшируются по тайтлу: свежий прогон зовёт подмену
run(sku="SKU-GRIND")
check("ключи размечены по нынешнему тайтлу снапшота ASIN ES", STATE.get("keys_title") == PILOT["B0H75P364R"]["title"])
_st_mod.cache_data.clear()
at = run(sku="SKU-TWO")
check("ASIN ES не один — тайтла снапшота нет, ключи без него (не по чужому ASIN)", STATE.get("keys_title") == "")

# ================================================================ сбои
import streamlit as st  # noqa: E402

st.cache_data.clear()                 # удачные чтения прошлых прогонов законно в кеше
STATE["load_err"] = "OperationalError: база недоступна"
at = run(sku="SKU-GRIND")
check("сбой снапшота — ошибка с причиной, страница не падает и ручная проверка на месте",
      not at.exception and any("база недоступна" in str(e.value) for e in at.error) and block5(at) is not None)
STATE["load_err"] = None
at = run(sku="SKU-GRIND")
check("сбой не закеширован: база ответила — ошибки нет", not any("база недоступна" in str(e.value) for e in at.error))

st.cache_data.clear()
STATE["keys_err"] = "OperationalError: SQP недоступен"
at = run(sku="SKU-GRIND")
full = texts_of(at)
check("сбой ключей — ошибка, а не «данных поиска нет»",
      "SQP недоступен" in full and lab("tg.keys_empty", n=0) not in full)
STATE["keys_err"] = None
at = run(sku="SKU-GRIND")
check("сбой ключей не закеширован", lab("tg.keys_from", n=3) in texts_of(at))
TYPE_ERR["err"] = "листинги недоступны"
at = run(sku="SKU-GRIND")
check("тип не прочитался — причина названа, правила инструмента, ключей по типу нет",
      lab("tg.gen.type_error", err="листинги недоступны") in texts_of(at)
      and lab("tg.gen.type_unknown") in texts_of(at) and lab("tg.keys_no_type") in texts_of(at))
TYPE_ERR["err"] = None

for lang in ("uk", "en"):
    # один прогон: подписи списка «Товар» строятся t() на языке страницы, а AppTest при
    # вводе пересчитывает их в процессе теста — на другом языке они не сошлись бы
    at = run(sku="SKU-GRIND", lang=lang)
    check(f"{lang}: страница открывается, подписи на своём языке",
          not at.exception and lab("tg.b5.title", lang) in [e.label for e in at.expander])

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
           | {"tg.where.title", "tg.where.highlights", "auth.role.textgen_pilot"}
           | {f"tg.b1.why.{c}" for c in tg.ASIN_CODES} | {"tg.gen.err.NO_PASSPORT"})
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
_st.cache_data.clear()
GEN["calls"].clear()
at = run()
check("у выбранного SKU — его ASIN ES (справочник по точному коду)",
      lab("tg.b1.asin", asin="B0GTRY26HB") in texts_of(at))
at.button(key="tg-gen-go").click().run()
check("генерация получает ASIN товара ES",
      GEN["calls"] and GEN["calls"][-1]["asins"] == ["B0GTRY26HB"] and GEN["calls"][-1]["marketplace"] == "es")
check("вариант 99601000-B не сопоставляется с базовым 99601000 матрицы по догадке",
      tg.asins_for_sku("99601000-B", None, MX["es"]) == [])

# Сбой источника — «не прочитано», а не «не найдено» (проверка #168).
LINK["err"] = "OperationalError: kabinet down"
_st.cache_data.clear()
at = run()
check("справочник не прочитан — сказано, ASIN «связь не прочитана», а не «нет ASIN ES»",
      "kabinet down" in texts_of(at) and lab("tg.b1.asin_none", why=lab("tg.b1.why.ASIN_UNREAD")) in texts_of(at)
      and lab("tg.b1.why.ASIN_UNKNOWN") not in texts_of(at))
GEN["calls"].clear()
at.button(key="tg-gen-go").click().run()
check("связь не прочитана — генерации уходит «не прочитано» (None), а не неполный список",
      GEN["calls"] and GEN["calls"][-1]["asins"] is None)
LINK["err"] = None
check("ASIN справочника с другого рынка не выдаётся за ES",
      tg.asins_for_sku("99601000-B", pd.DataFrame([{"sku": "99601000-B", "asins": "B0GTRY26HB B0DEDEDEDE"}]),
                       MX["es"]) == ["B0GTRY26HB"])
check("без матрицы ES не проверить — ответ пустой", tg.asins_for_sku("99601000-B", DIR, None) == [])
NAN_DIR = pd.DataFrame([{"sku": "99601000-B", "asins": float("nan")}, {"sku": float("nan"), "asins": "B0GTRY26HB"}])
check("NaN в ячейке справочника — не «nan» (правило 4)",
      "nan" not in tg.asins_for_sku("99601000-B", NAN_DIR, MX["es"])
      and "nan" not in tg.skus_for_asin("B0GTRY26HB", NAN_DIR, MX["es"]))
check("конкуренты в связь не идут (запрос матрицы)", "is_competitor IS NOT TRUE" in SRC)
# «$» внутри `кода` не экранируется: там обратная косая осталась бы на экране.
_st.cache_data.clear()
at = run(sku="SKU-GRIND", title="DNIPRO-M Amoladora $ 125mm")
check("запрещённый «$» в тайтле назван как `$`, без обратной косой",
      any("`$`" in str(m.value) for m in at.markdown) and not any("`\\$`" in str(m.value) for m in at.markdown))

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
# --- один выбор на всю страницу, общий с «Паспорт SKU» в обе стороны (решение
# владельца 29.10.2026): генератор всегда на pp-sku и своего SKU не держит.
import services.passport as _pp_svc  # noqa: E402
import components.passport_area as _parea  # noqa: E402

GEN["copies"] = (pd.DataFrame([dict(GEN["copies"][0].iloc[0]),
                               {"source_artifact_id": "DOCX-PASS-21680000-001-v1", "sku_id": "21680000",
                                "passport_id": "PASS-21680000-001", "sha256": "1" * 64,
                                "archived_locator": "/Volumes/dnipro_m/listing_data/passports/y.docx",
                                "recorded_at": "2026-10-28"}]), None)
at = run(sku="21680000")
check("генератор на SKU, выбранном в «Паспорт SKU» (pp-sku)", picker(at)[0].value == "21680000")
GEN["calls"].clear()
at.button(key="tg-gen-go").click().run()
check("генерация — по выбранному SKU, тип товара уходит в генерацию (аккумулятор)",
      GEN["calls"] and GEN["calls"][-1]["sku"] == "21680000" and GEN["calls"][-1].get("tool_type") == "battery")
picker(at)[0].set_value("99601000-B").run()
check("выбор в генераторе меняет общий выбор — «Паспорт SKU» и Верификатор на нём же",
      at.session_state["pp-sku"] == "99601000-B")
GEN["calls"].clear()
at.button(key="tg-gen-go").click().run()
check("и генерация сразу по нему", GEN["calls"] and GEN["calls"][-1]["sku"] == "99601000-B")
KEEP = ("lang", "pp-sku", "pp-sku-gen")


def reenter(prev, **change):
    nxt = AppTest.from_file(str(PAGE), default_timeout=60)
    for k in KEEP:
        if k in prev.session_state:
            nxt.session_state[k] = prev.session_state[k]
    for k, v in change.items():
        nxt.session_state[k] = v
    return nxt.run()


at = reenter(at, **{"pp-sku": "21680000"})          # товар сменили в «Паспорт SKU»
check("сменили в «Паспорт SKU» — генератор на нём, без своего выбора", picker(at)[0].value == "21680000")
at = reenter(at)
check("повторный заход — тот же общий товар", picker(at)[0].value == "21680000")
check("старых ключей своего выбора нет", not any(k in at.session_state for k in ("tg-gen-choice", "tg-gen-ctx")))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
