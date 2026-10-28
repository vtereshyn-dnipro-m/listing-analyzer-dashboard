# -*- coding: utf-8 -*-
"""
tests/test_passport_sku_picker.py — выпадающий список товаров в Реестре Паспортов
(поручение владельца 28.10.2026). Без сети: базы Listing Suite и Кабинета подменены.

Что заперто:
  · список тянется сам из справочника SKU Кабинета, руками товары не вводятся;
  · в строке — SKU, название, тип и статус паспорта: «паспорт v2, «В работе»» или
    «Паспорт отсутствует»;
  · тип — из данных листинга ES (тайтл и productType), по ASIN справочника и по
    точному sku_group матрицы; не определён — так и сказано;
  · выбор в списке — точный выбор SKU контекста: его видят «Создание», карточка,
    «Верификатор»; карточка показывается и для товара вне текущего поиска;
  · справочник не прочитался — ошибка над списком, а в списке товары с паспортом;
  · ручной поиск по SKU, названию, модели, ASIN и EAN работает как раньше;
  · тип определяет правила генерации: аккумулятор и зарядка — вольтаж в тайтле
    можно, инструмент и неизвестный тип — нельзя; тип называется в промпте.

Запуск (pytest не нужен):  python tests/test_passport_sku_picker.py
"""
from __future__ import annotations

import hashlib
import io
import pathlib
import sys
import zipfile

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
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


body = (_p("Паспорт SKU 99601000-B", "Title")
        + _tbl([("Параметр", "Значення"), ("passport_id", "PASS-99601000-B-001"), ("passport_version", "2"),
                ("state", "NOT_READY"), ("sku_id", "99601000-B")])
        + _p("Ідентичність товару", "Heading1")
        + _tbl([("Поле", "Значення", "Статус", "Джерело"), ("Модель", "DVB-200BC Dual", "PROPOSED", "SRC-1")]))
_b = io.BytesIO()
with zipfile.ZipFile(_b, "w") as z:
    z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
               f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
DOCX = _b.getvalue()
SHA = hashlib.sha256(DOCX).hexdigest()
LOC = "/Volumes/dnipro_m/listing_data/passports/99601000-B/PASS-99601000-B-001/v2/PASS-99601000-B-001_v2.docx"
TS = pd.Timestamp("2026-10-21 18:05", tz="UTC")

DIRECTORY = pd.DataFrame([
    dict(sku="99601000-B", name="Пилосос садовий DVB-200BC Dual", ean="4823102367354", is_active=True,
         asins="B0GTRY26HB"),
    dict(sku="21680000", name="Насос поверхностный PW-14B", ean="4823102300001", is_active=True, asins=""),
    dict(sku="55550000", name="Акумулятор BP-240 4 Ah", ean="", is_active=True, asins="B0BAT00001"),
    dict(sku="77770000", name="Стрічка без листинга", ean="", is_active=True, asins=""),
])
COPY = pd.DataFrame([dict(source_artifact_id="DOCX-PASS-99601000-B-001-v2", sku_id="99601000-B",
                          passport_id="PASS-99601000-B-001", archived_locator=LOC, sha256=SHA, bytes=len(DOCX),
                          lifecycle="ACTIVE", registered_by="a", recorded_at=TS)])
# Листинги ES: тип узнаётся по тайтлу и productType, SKU — по ASIN справочника или sku_group.
LISTING = pd.DataFrame([
    dict(asin="B0GTRY26HB", sku_group="99601000", title="Aspirador Soplador de Jardín Dnipro-M DVB-200BC Dual 20V",
         product_type="LEAF_BLOWER", mp="es", competitor=False),
    dict(asin="B0PUMP0001", sku_group="21680000", title="Bomba de superficie Dnipro-M PW-14B 1100W", product_type=None,
         mp="es", competitor=False),
    dict(asin="B0BAT00001", sku_group="", title="Batería de litio Dnipro-M BP-240 20V 4Ah", product_type="BATTERY",
         mp="es", competitor=False),
    # ловушки фикстуры: конкурент с нашим sku_group, листинг не ES — в типы не идут
    dict(asin="B0COMP0001", sku_group="21680000", title="Batería Makita 18V", product_type="BATTERY",
         mp="es", competitor=True),
    dict(asin="B0COMP0002", sku_group="21680000", title="Batería Bosch 18V", product_type="BATTERY",
         mp="es", competitor=True),
    dict(asin="B0DE000001", sku_group="77770000", title="Taladro Dnipro-M", product_type="DRILL",
         mp="de", competitor=False),
])
# Последний снапшот B0BAT00001 — неудачный, с чужим тайтлом: без «s.ok IS TRUE» тип был бы зарядкой.
FAILED_TITLE = {"B0BAT00001": "Cargador rápido Dnipro-M"}
MODE = {"dir_fail": False, "listing_fail": False}


def fake_sql(sql, con=None, params=None, **kw):
    q = " ".join(str(sql).split())
    if "to_regclass" in q:
        return pd.DataFrame([{"t": (params or {}).get("n", "")}])
    if "FROM passport_source_artifacts" in q:
        return COPY.copy()
    if "FROM product_matrix pm LEFT JOIN LATERAL" in q:
        if MODE["listing_fail"]:
            raise RuntimeError("листинги недоступны")
        df = LISTING.copy()
        if "pm.marketplace = 'es'" in q:
            df = df[df["mp"] == "es"]
        if "pm.is_competitor IS NOT TRUE" in q:
            df = df[~df["competitor"]]
        if "s.ok IS TRUE" not in q:
            df["title"] = [FAILED_TITLE.get(a, ttl) for a, ttl in zip(df["asin"], df["title"])]
        return df[["asin", "sku_group", "title", "product_type"]]
    if q.startswith("SELECT asin, sku_group FROM product_matrix WHERE marketplace"):
        return LISTING[(LISTING["mp"] == "es") & ~LISTING["competitor"]][["asin", "sku_group"]].copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
import services.db as db  # noqa: E402
db.get_conn = lambda: type("C", (), {"close": lambda self: None})()


class _Cur:
    def __init__(self):
        self.description, self._rows = [], []

    def execute(self, sql, params=None):
        if "sku_master" not in sql or MODE["dir_fail"]:
            raise RuntimeError("Кабинет недоступен")
        self.description = [(c,) for c in DIRECTORY.columns]
        self._rows = [tuple(r) for r in DIRECTORY.itertuples(index=False)]

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _KConn:
    def cursor(self):
        return _Cur()

    def close(self):
        pass


import services.kdb as kdb  # noqa: E402
kdb.get_conn = lambda: _KConn()
from services import passport_copies as pc  # noqa: E402

pc.volume_store = lambda: type("S", (), {"get": lambda self, loc: DOCX})()
from services import product_specs as ps  # noqa: E402

ps.load = lambda asin, mp: (None, "нет снапшота в тесте")
import services.passport as pp  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from i18n import t  # noqa: E402
from services import textgen as tg  # noqa: E402
from services import title_rules as tr  # noqa: E402

# ================================================================ сервис
print("тип товара — из данных листинга")
st.cache_data.clear()
listing, lerr = pp.listing_types_es()
types = pp.sku_types(DIRECTORY, listing)
check("листинги ES прочитаны, тип узнан по тайтлу и productType удачного снапшота; конкуренты и не ES — нет",
      lerr is None and dict(zip(listing["asin"], listing["type"])) == {"B0GTRY26HB": "blower", "B0PUMP0001": "pump",
                                                                       "B0BAT00001": "battery"})
check("SKU → тип: по ASIN справочника (99601000-B, 55550000) и по точному sku_group (21680000)",
      types == {"99601000-B": "blower", "21680000": "pump", "55550000": "battery"})
check("у SKU без листинга ES типа нет — не выдумывается", "77770000" not in types)
mixed = pd.DataFrame([dict(asin="A1", sku_group="X", type="drill"), dict(asin="A2", sku_group="X", type="hammer"),
                      dict(asin="A3", sku_group="X", type="hammer")])
check("разные типы у одного SKU — самый частый, стабильно",
      pp.sku_types(pd.DataFrame([dict(sku="X", asins="")]), mixed) == {"X": "hammer"})
# Настоящая форма: тип не узнан → detect_type даёт None, а столбец, собранный тем же
# pd.DataFrame(rows, columns=…), что в listing_types_es, хранит NaN (строковый столбец
# pandas 3). У SKU один листинг с типом, другой без — так упал Реестр на проде 28.10.2026.
real = pd.DataFrame([{"asin": "B1", "sku_group": "Y", "type": "drill"},
                     {"asin": "B2", "sku_group": "Y", "type": None},
                     {"asin": "B3", "sku_group": "Z", "type": None}], columns=["asin", "sku_group", "type"])
try:
    got = pp.sku_types(pd.DataFrame([dict(sku="Y", asins="B1 B2"), dict(sku="Z", asins="B3")]), real)
except TypeError as e:
    got = e
check("тип не узнан у части листингов SKU (NaN в столбце) — без падения, тип по узнанным; "
      "SKU только с неузнанными — без типа, а не «nan»", got == {"Y": "drill"})
MODE["listing_fail"] = True
st.cache_data.clear()
_l, _e = pp.listing_types_es()
check("листинги не прочитались — причина, а не пустота «типов нет»", _e is not None and _l.empty)
MODE["listing_fail"] = False
_l2, _e2 = pp.listing_types_es()
check("сбой листингов не кэшируется: база вернулась — типы сразу, без чистки кэша (проверка #178)",
      _e2 is None and not _l2.empty)
check("правила по типу: аккумулятор и зарядка — POWER_PACK, инструмент и неизвестный — TOOL",
      tg.kind_of("battery") == tr.POWER_PACK and tg.kind_of("charger") == tr.POWER_PACK
      and tg.kind_of("blower") == tr.TOOL and tg.kind_of(None) == tr.TOOL and tg.kind_of("unknown") == tr.TOOL)
texts = {f: "VALOR: texto" for f in tg.FIELDS}
texts.update(title="DNIPRO-M Batería BP-240 20V, 4Ah", highlight="Model BP-240: batería 20V")
codes = lambda kind: {v["code"] for v in tg.run_checks(texts, "BP-240", kind=kind)}  # noqa: E731
check("вольтаж в тайтле: у аккумулятора можно, у инструмента — TOOL_VOLTAGE",
      "TOOL_VOLTAGE" not in codes(tr.POWER_PACK) and "TOOL_VOLTAGE" in codes(tr.TOOL))
from services import passport_facts as pf  # noqa: E402

prompt = tg.build_prompt("55550000", "es", {"passport_id": "P", "passport_version": "1"}, pf.Facts([], []), "battery")
check("тип назван в промпте вместе с правилом", "Тип товара (из листинга, код): battery" in prompt
      and "вольтаж в тайтле можно" in prompt)
check("без типа строки о типе нет", "Тип товара" not in tg.build_prompt("X", "es", {}, pf.Facts([], [])))
class GenDB:
    """Минимальная база генерации: журнал вызовов, решения, черновики."""

    def __init__(self):
        self.res, self.content = [], []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self

    def execute(self, sql, p=()):
        if sql.startswith("SELECT to_regclass('listing_data.passport_conflict_decisions')"):
            self.res = [(False,)]
        elif "pg_advisory_xact_lock" in sql or sql.startswith("SELECT to_regclass"):
            self.res = [(True,)]
        elif "information_schema.columns" in sql:
            self.res = [(0,)]
        elif sql.startswith("SELECT count(*)"):
            self.res = [(0, 0, 0)]
        elif sql.startswith("INSERT INTO textgen_calls"):
            self.res = [(1,)]
        elif sql.startswith("SELECT COALESCE(max(version)"):
            self.res = [(0,)]
        elif sql.startswith("INSERT INTO content_versions"):
            self.content.append(p)
            self.res = []
        else:
            self.res = []

    def fetchone(self):
        return self.res[0] if self.res else None

    def fetchall(self):
        return list(self.res)


ANSWER = {"title": "DNIPRO-M Batería BP-240 20V, 4Ah", "highlight": "Model BP-240: batería 20V",
          "bullets": ["VALOR: texto"] * 5, "description": "Texto."}
SEEN = {}


def gen(tool_type):
    def ai_call(task, prompt, system=None):
        SEEN["prompt"] = prompt
        return ANSWER
    return tg.generate(sku="99601000-B", marketplace="es", copy={"source_artifact_id": "DOCX-PASS-99601000-B-001-v2",
                       "passport_id": "PASS-99601000-B-001", "archived_locator": LOC, "sha256": SHA}, actor="y",
                       store=type("S", (), {"get": lambda self, loc: DOCX})(), conn=GenDB(), method=("методология", 2),
                       provider="anthropic", model="claude-opus-5-5", max_tokens=100, setting=lambda k, d="": d,
                       ai_call=ai_call, ai_usage=lambda: {}, ai_reset=lambda: None, asins=["B0GTRY26HB"],
                       tool_type=tool_type)


r_bat, r_tool = gen("battery"), gen(None)
check("генерация: тип «аккумулятор» доходит до проверок — вольтаж в тайтле не нарушение",
      r_bat.status == "OK" and "TOOL_VOLTAGE" not in {c["code"] for c in r_bat.checks})
check("генерация: тип неизвестен — правила инструмента, TOOL_VOLTAGE", "TOOL_VOLTAGE" in {c["code"] for c in r_tool.checks})
gen("battery")
check("генерация: тип назван в промпте", "Тип товара (из листинга, код): battery" in SEEN["prompt"])


# ================================================================ экран
def page(**state):
    st.cache_data.clear()
    st.cache_resource.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.switch_page("pages/content.py")
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def texts_of(at) -> str:
    out = []
    for coll in (at.markdown, at.caption, at.info, at.warning, at.error, at.success):
        out += [str(x.value) for x in coll]
    return "\n".join(out)


def picker(at):
    return next((s for s in at.selectbox if str(s.key).startswith("pp-pick-")), None)


def ctx(at):
    return at.session_state["pp-sku"] if "pp-sku" in at.session_state else None


print("список в Реестре")
at = page(**{"pp-tab": "registry"})
check("Реестр со списком открывается", not at.exception)
sb = picker(at)
check("список есть и тянется из справочника: все SKU справочника, без ручного ввода",
      sb is not None and list(sb.options)[1:] and set(sb.proto.options[1:]) and len(sb.options) == 1 + len(DIRECTORY))
labels = list(sb.options) if sb else []
lab_996 = next((x for x in labels if x.startswith("99601000-B")), "")
lab_216 = next((x for x in labels if x.startswith("21680000")), "")
lab_777 = next((x for x in labels if x.startswith("77770000")), "")
check("строка с паспортом: SKU, название, тип, «паспорт v2, «В работе»»",
      lab_996 == " · ".join(["99601000-B", "Пилосос садовий DVB-200BC Dual", t("tg.type.blower"),
                             t("pp.pick.has", ver="2", state=t("pp.state.NOT_READY"))]))
check("строка без паспорта: «Паспорт отсутствует», тип из листинга",
      lab_216 == " · ".join(["21680000", "Насос поверхностный PW-14B", t("tg.type.pump"), t("pp.pick.absent")]))
check("без листинга ES — «тип не определён», а не пусто", t("pp.pick.type_unknown") in lab_777)
check("пока не выбрано — пункт «выберите товар»", sb is not None and sb.value == "")

sb.set_value("21680000").run()
check("выбор в списке — точный SKU контекста", ctx(at) == "21680000")
sb2 = picker(at)
check("после выбора список пересоздан на выбранном SKU (ключ несёт контекст, правило 7б)",
      sb2 is not None and sb2.key == "pp-pick-21680000" and sb2.value == "21680000")
check("карточка выбранного товара показана, хотя без поиска его нет в таблице (паспорта нет)",
      any("Насос поверхностный PW-14B" in str(m.value) and "21680000" in str(m.value) for m in at.markdown)
      and t("pp.pick_hint") not in texts_of(at))
at.session_state["pp-tab"] = "create"
at.run()
check("«Создание» видит тот же SKU", "21680000" in texts_of(at) and not at.exception)
at.session_state["pp-tab"] = "verifier"
at.run()
check("«Верификатор» на том же SKU (он в заголовке вкладки), у товара без копии блока конфликтов нет",
      any('class="ls-mono"' in str(m.value) and "21680000" in str(m.value) for m in at.markdown)
      and not any(str(b.key).startswith("pp-cfd-save-") for b in at.button) and not at.exception)
at.session_state["pp-tab"] = "registry"
at.run()
picker(at).set_value("").run()
check("пустой пункт — явный сброс товара: контекста и карточки нет (проверка #178)",
      ctx(at) is None and not any("Насос поверхностный PW-14B" in str(m.value) for m in at.markdown)
      and picker(at).value == "")

at = page(**{"pp-tab": "registry"})
picker(at).set_value("21680000").run()
at.session_state["pp-sku"] = "99601000-B"           # выбор в другом месте (строка Реестра, «Сменить товар»)
at.run()
check("SKU выбран в другом месте — список стоит на нём, прежний выбор не возвращается (правило 7б)",
      picker(at) is not None and picker(at).value == "99601000-B" and ctx(at) == "99601000-B")

print("клик по строке таблицы после выбора в списке")
at = page(**{"pp-tab": "registry"})
picker(at).set_value("21680000").run()
gen = lambda: at.session_state["pp-sku-gen"] if "pp-sku-gen" in at.session_state else 0  # noqa: E731
g0 = gen()
check("выбор в списке растит поколение выбора (по нему генератор видит новое действие)", g0 >= 1)
first = next(d.value for d in at.dataframe if isinstance(d.value, pd.DataFrame) and "next" in d.value.columns)
from components import passport_area as _pa  # noqa: E402
at.session_state[_pa.table_key(list(first["sku"].astype(str)))] = {"selection": {"rows": [0], "columns": [], "cells": []}}
at.run()
row0 = first.iloc[0]["sku"]
check(f"клик по строке ({row0}) — контекст и список на нём в этом же прогоне (проверка #178)",
      ctx(at) == row0 and picker(at).value == row0)
at.run()
check("следующий прогон — выделение строки не перебивает и не мигает", ctx(at) == row0 and picker(at).value == row0)
check("клик по строке растит поколение выбора, повторный прогон — нет", gen() == g0 + 1)
picker(at).set_value("21680000").run()
check("после клика по строке выбор в списке снова работает", ctx(at) == "21680000" and picker(at).value == "21680000")
g1 = gen()
at.session_state["pp-sku"] = "99601000-B"
at.run()
g2 = gen()
opened = [b for b in at.button if b.key == "pp-open"]
if opened:
    opened[0].click().run()
check("«Открыть Паспорт» того же товара — товар не сменился, поколение выбора прежнее "
      "(решение владельца 28.10.2026)",
      bool(opened) and ctx(at) == "99601000-B" and gen() == g2)
at.button(key="pp-change").click().run()
check("«Сменить товар» — сброс и новое поколение выбора", ctx(at) is None and gen() == g2 + 1)

print("копия не прочиталась / листинги не прочитались")
_store = pc.volume_store
pc.volume_store = lambda: None
at = page(**{"pp-tab": "registry"})
lab = next((x for x in picker(at).options if x.startswith("99601000-B")), "")
check("копия есть, но не прочиталась — «паспорт v—, не прочитан», а не «Паспорт отсутствует»",
      t("pp.pick.unread", ver="—") in lab and t("pp.pick.absent") not in lab)
pc.volume_store = _store
MODE["listing_fail"] = True
at = page(**{"pp-tab": "registry"})
check("листинги не прочитались — причина названа над списком, тип «не определён»",
      any(str(c.value).startswith(t("pp.pick.type_error", err="X").split(":")[0]) for c in at.caption)
      and all(t("pp.pick.type_unknown") in x for x in picker(at).options[1:]))
MODE["listing_fail"] = False

print("ручной поиск — запасной путь")
for q in ("PW-14B", "21680000", "4823102300001", "dvb-200bc", "B0GTRY26HB"):
    at = page(**{"pp-tab": "registry", "pp-q": q})
    tbl = next((d.value for d in at.dataframe if isinstance(d.value, pd.DataFrame) and "sku" in d.value.columns
                and "next" in d.value.columns), pd.DataFrame())
    check(f"поиск «{q}» работает", not tbl.empty)

print("справочник не прочитался")
MODE["dir_fail"] = True
at = page(**{"pp-tab": "registry"})
sb = picker(at)
check("ошибка над списком, а не пустой список молча",
      any(str(e.value).startswith(t("pp.pick.dir_error", err="X").split(":")[0]) for e in at.error))
check("в списке остаются товары с паспортом", sb is not None and any(x.startswith("99601000-B") for x in sb.options))
MODE["dir_fail"] = False

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
