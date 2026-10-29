# -*- coding: utf-8 -*-
"""
tests/test_passport_type_filter.py — фильтр «Тип товара» и массовый выбор в Реестре
Паспортов (поручение владельца 28.10.2026). Без сети: базы подменены.

Что заперто:
  · значения фильтра — из данных тем же определителем, что у генератора
    (sku_types / detect_type по листингам ES): «Любой», каждый найденный тип и
    «тип не определён», с числом товаров по всему справочнику;
  · фильтр сужает список «Товар», массовый выбор и таблицу (правило 8); счётчики
    списка (весь справочник) и таблицы (товары с паспортом) названы раздельно;
  · примеры владельца: Воздуходувка — 99601000-B, Болгарка — 08455000,
    Аккумулятор — 08456000, «тип не определён» — 08087000 и не распознанные,
    «Любой» — все;
  · массовый выбор: виден списком (SKU, название, тип, статус паспорта), снятие и
    очистка явные; «Выбрать все» — только внутри типа;
  · смена фильтра: в выборе остаются только товары нового типа, снятые названы
    сообщением, молча не держатся;
  · пустой результат и пропавший тип не роняют страницу;
  · массовых действий нет: ни генерации, ни принятия, ни отправки.

Запуск (pytest не нужен):  python tests/test_passport_type_filter.py
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
    dict(sku="99601000-B", name="Пилосос садовий DVB-200BC Dual", ean="", is_active=True, asins="B0GTRY26HB"),
    dict(sku="08455000", name="Болгарка акумуляторна CG-12BC Ultra", ean="", is_active=True, asins=""),
    dict(sku="08455001", name="Болгарка CG-125", ean="", is_active=True, asins="B0GRIND002"),
    dict(sku="08456000", name="Акумулятор BP-125 12V 4Ah", ean="", is_active=True, asins=""),
    dict(sku="08087000", name="Pistola de calor Dnipro-M GH-201N", ean="", is_active=True, asins="B0HEAT0001"),
    dict(sku="77770000", name="Стрічка без листинга", ean="", is_active=True, asins=""),
    # знаки разметки в SKU — сообщение о снятых их экранирует
    dict(sku="7777_*01", name="Спецсимволы", ean="", is_active=True, asins=""),
])
COPY = pd.DataFrame([dict(source_artifact_id="DOCX-PASS-99601000-B-001-v2", sku_id="99601000-B",
                          passport_id="PASS-99601000-B-001", archived_locator=LOC, sha256=SHA, bytes=len(DOCX),
                          lifecycle="ACTIVE", registered_by="a", recorded_at=TS)])
# Листинги ES с живыми тайтлами 28.10.2026: тип — по ASIN справочника или точному sku_group
LISTING = pd.DataFrame([
    dict(asin="B0GTRY26HB", sku_group="99601000",
         title="Aspirador Soplador de Jardín Dnipro-M DVB-200BC Dual 20V, Triturador 15:1", product_type="LEAF_BLOWER"),
    dict(asin="B0DG5YPX5B", sku_group="08455000",
         title="Amoladora Angular Inalámbrica CG-12BC Ultra 12V Brushless - Dnipro-M", product_type="DISC_GRINDER_TOOL"),
    dict(asin="B0GRIND002", sku_group="",
         title="Amoladora Angular Dnipro-M CG-125 1200W 125 mm", product_type="DISC_GRINDER_TOOL"),
    dict(asin="B0DFZ21DF8", sku_group="08456000",
         title="Batería Dnipro-M BP-125 12V 4Ah Li-Ion para Herramientas DM12 Protegida", product_type="BATTERY"),
])
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
        return LISTING.copy()
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

from components import passport_area as pa  # noqa: E402
from i18n import t  # noqa: E402

ALL = sorted(DIRECTORY["sku"])
DROPPED = t("pp.multi.dropped", n=0, ty="", skus="").split("«")[0]     # начало сообщения о снятых


def page(**state):
    st.cache_data.clear()
    st.cache_resource.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.switch_page("pages/content.py")
    at.session_state["pp-tab"] = "registry"
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def ftype(at):
    return at.selectbox(key="pp-type")


def picker(at):
    return next((s for s in at.selectbox if str(s.key).startswith("pp-pick-")), None)


def multi(at):
    return next((m for m in at.multiselect if str(m.key).startswith("pp-multi-w-")), None)


def sel(at):
    return list(at.session_state["pp-multi"]) if "pp-multi" in at.session_state else []


def texts_of(at) -> str:
    out = []
    for coll in (at.markdown, at.caption, at.info, at.warning, at.error, at.success):
        out += [str(x.value) for x in coll]
    return "\n".join(out)


print("значения фильтра — из данных")
at = page()
check("Реестр с фильтром типа открывается", not at.exception)
f = ftype(at)
opts = list(f.options)
check("варианты: «Любой (6)», каждый найденный тип с числом, «тип не определён» с числом — последним",
      opts[0] == pa.type_label("any", 7) and opts[-1] == f"{t('pp.pick.type_unknown')} (3)"
      and f"{t('tg.type.grinder')} (2)" in opts and f"{t('tg.type.blower')} (1)" in opts
      and f"{t('tg.type.battery')} (1)" in opts and len(opts) == 5)
check("«тип не определён», а не «nan»", not any("nan" in o.lower() for o in opts))
check("по умолчанию «Любой» — в списке «Товар» все товары справочника",
      f.value == "any" and sorted(o for o in picker(at).options if o and o != t("pp.pick.none")) != []
      and len(picker(at).options) == len(ALL) + 1)


def only(code):
    at = page(**{"pp-type": code})
    opts = [o.split(" · ")[0] for o in picker(at).options[1:]]
    return at, opts


at, o = only("blower")
check("Воздуходувка: в списке 99601000-B, и только он", o == ["99601000-B"] and not at.exception)
check("счётчики раздельно: список — весь справочник «1 из 7», таблица — товары с паспортом: найдено и показано",
      t("pp.type.counts", ty=t("tg.type.blower"), k=1, all=7, found=1, shown=1) in texts_of(at))
check("«Найдено / показано» над таблицей — та же выборка под типом",
      t("pp.found", n=1, shown=1) in texts_of(at))
at, o = only("grinder")
check("Болгарка: 08455000 (и второй болгарки SKU), без прочих", o == ["08455000", "08455001"])
check("Болгарка: таблица (товары с паспортом) пуста — страница не падает, сказано словами",
      not at.exception and t("pp.type.counts", ty=t("tg.type.grinder"), k=2, all=7, found=0, shown=0) in texts_of(at))
check("пустая под типом таблица — «нет товаров этого типа», а не «Паспортов пока нет»",
      any(t("pp.type.empty", ty=t("tg.type.grinder")) in str(i.value) for i in at.info)
      and not any(t("pp.empty_hint") in str(i.value) for i in at.info))
at, o = only("battery")
check("Аккумулятор: 08456000", o == ["08456000"])
at, o = only("unknown")
check("«тип не определён»: 08087000 GH-201N и прочие нераспознанные, без распознанных",
      o == ["08087000", "77770000", "7777_*01"] and "99601000-B" not in o and "08455000" not in o)
at, o = only("any")
check("«Любой» возвращает все товары", o == ALL)
at = page(**{"pp-type": "drill"})
check("тип, которого нет в данных, — «Любой», без падения", not at.exception and ftype(at).value == "any")
check("на «Любом» подписи счётчиков типа нет", not any(t("pp.type.counts", ty="", k=0, all=0, found=0, shown=0)
                                                       .split("«")[0] in str(c.value) for c in at.caption))

print("поиск и предел строк")
_lim = pp.SEARCH_LIMIT
pp.SEARCH_LIMIT = 2
at = page(**{"pp-type": "battery", "pp-q": "0"})
check("тип режется до предела поиска: «0» находит все SKU, но под «Аккумулятором» в таблице 08456000",
      not at.exception and t("pp.found", n=1, shown=1) in texts_of(at)
      and any("08456000" in list(d.value.get("sku", [])) for d in at.dataframe if hasattr(d.value, "get")))
at = page(**{"pp-type": "grinder", "pp-q": "zzz"})
check("по запросу под типом ничего — «по запросу товаров типа не найдено»",
      any(t("pp.type.empty_q", ty=t("tg.type.grinder"), q="zzz") in str(i.value) for i in at.info))
pp.SEARCH_LIMIT = _lim

print("выделенная строка таблицы и смена типа")
at = page(**{"pp-type": "grinder", "pp-q": "0845"})
first = next(d.value for d in at.dataframe if hasattr(d.value, "columns") and "next" in d.value.columns)
at.session_state[pa.table_key(list(first["sku"].astype(str)))] = {"selection": {"rows": [1], "columns": [], "cells": []}}
at.run()
picked = first.iloc[1]["sku"]
check(f"клик по второй строке — товар {picked}", at.session_state["pp-sku"] == picked)
ftype(at).set_value("battery").run()
check("сменили тип — строк меньше: без падения, товар карточки тот же (смена товара только явная)",
      not at.exception and at.session_state["pp-sku"] == picked)
ftype(at).set_value("grinder").run()
check("вернули тип — прежнее выделение не переключает карточку молча",
      not at.exception and at.session_state["pp-sku"] == picked)

print("массовый выбор")
at = page(**{"pp-type": "grinder"})
check("варианты массового выбора — только товары типа",
      [o.split(" · ")[0] for o in multi(at).options] == ["08455000", "08455001"])
check("«Выбрать все» доступна внутри типа и называет число", not at.button(key="pp-multi-all").disabled
      and t("pp.multi.all", n=2) in str(at.button(key="pp-multi-all").label))
multi(at).set_value(["08455000", "08455001"]).run()
check("выбраны два товара типа — хранятся кодами отдельно от виджета", sel(at) == ["08455000", "08455001"])
tbl = next((d.value for d in at.dataframe if "passport" in getattr(d.value, "columns", [])), None)
check("выбранные видны списком: SKU, название, тип, статус паспорта по каждому",
      tbl is not None and list(tbl["sku"]) == ["08455000", "08455001"]
      and list(tbl["type"]) == [t("tg.type.grinder")] * 2 and list(tbl["passport"]) == [t("pp.pick.absent")] * 2
      and tbl["name"].iloc[0].startswith("Болгарка") and t("pp.multi.count", n=2) in texts_of(at))
multi(at).set_value(["08455001"]).run()
check("снятие одного — явно, остальные на месте", sel(at) == ["08455001"])
at.button(key="pp-multi-clear").click().run()
check("«Очистить выбор» — пусто, таблицы выбранных нет",
      sel(at) == [] and not any("passport" in getattr(d.value, "columns", []) for d in at.dataframe))
check("«Очистить» выключена, когда выбирать нечего", at.button(key="pp-multi-clear").disabled)
at.button(key="pp-multi-all").click().run()
check("«Выбрать все в фильтре» — ровно товары типа, без ложного сообщения о снятых",
      sel(at) == ["08455000", "08455001"] and list(multi(at).value) == ["08455000", "08455001"]
      and not any(DROPPED in str(i.value) for i in at.info))
at.run()
check("и на следующем прогоне ничего не снято", sel(at) == ["08455000", "08455001"]
      and not any(DROPPED in str(i.value) for i in at.info))
check("выбор не меняет товар карточки: контекст не тронут", "pp-sku" not in at.session_state)

print("смена фильтра с выбранным списком")
ftype(at).set_value("battery").run()
check("сменили тип — товары вне фильтра сняты, сообщение называет сколько и какие",
      sel(at) == [] and any(t("pp.multi.dropped", n=2, ty=t("tg.type.battery"), skus="08455000, 08455001")
                            in str(i.value) for i in at.info))
check("поле выбора пересоздано на новом наборе — снятые не висят в виджете", list(multi(at).value) == [])
ftype(at).set_value("blower").run()
check("следующая смена типа — устаревшее сообщение о снятых не висит",
      not any(DROPPED in str(i.value) for i in at.info))
at = page(**{"pp-type": "unknown"})
multi(at).set_value(["08087000", "7777_*01"]).run()
ftype(at).set_value("grinder").run()
from components.ui import md_escape  # noqa: E402
check("SKU со знаками разметки в сообщении экранированы",
      any(md_escape("08087000, 7777_*01") in str(i.value) for i in at.info))
at.button(key="pp-reset").click().run()
check("«Сбросить фильтры» — сообщение о снятых уходит", not any(DROPPED in str(i.value) for i in at.info))
at = page(**{"pp-type": "unknown"})
multi(at).set_value(["08087000", "77770000"]).run()
ftype(at).set_value("any").run()
check("на «Любой» выбор остаётся целиком — все товары в фильтре, сообщения нет",
      sel(at) == ["08087000", "77770000"] and not any(DROPPED in str(i.value) for i in at.info)
      and list(multi(at).value) == ["08087000", "77770000"])
check("«Выбрать все» на «Любой» выключена — все типы разом не выбираются",
      at.button(key="pp-multi-all").disabled)
check("на «Любом» поле выбора выключено, подпись «выберите тип»; выбранное видно и очищается",
      multi(at).disabled and t("pp.multi.need_type") in texts_of(at)
      and not at.button(key="pp-multi-clear").disabled
      and any("passport" in getattr(d.value, "columns", []) for d in at.dataframe))
ftype(at).set_value("grinder").run()
at.button(key="pp-reset").click().run()
check("«Сбросить фильтры» сбрасывает и тип: с «Болгарки» на «Любой»", ftype(at).value == "any")

print("пустой результат и сбои")
MODE["listing_fail"] = True
at = page(**{"pp-type": "grinder"})
check("листинги не прочитались — все товары «тип не определён», выбранный тип пропал → «Любой», без падения",
      not at.exception and ftype(at).value == "any" and list(ftype(at).options) == [
          pa.type_label("any", 7), f"{t('pp.pick.type_unknown')} (7)"])
MODE["listing_fail"] = False
MODE["dir_fail"] = True
at = page(**{"pp-type": "blower"})
check("справочник не прочитался — фильтр по паспортным товарам, ошибка над списком, без падения",
      not at.exception and any("Справочник SKU" in str(e.value) or "SKU directory" in str(e.value) for e in at.error))
MODE["dir_fail"] = False
at = page(**{"pp-type": "grinder"})
at.button(key="pp-multi-all").click().run()
MODE["dir_fail"] = True
st.cache_data.clear()
at.run()
check("сбой справочника не стирает выбор и не пишет ложную причину; сказано, что выбор не проверен",
      not at.exception and sel(at) == ["08455000", "08455001"] and not any(DROPPED in str(i.value) for i in at.info)
      and not any(t("pp.multi.gone", n=0, skus="").split(":")[0] in str(i.value) for i in at.info)
      and t("pp.multi.unchecked") in texts_of(at))
MODE["dir_fail"] = False
st.cache_data.clear()
at.run()
check("справочник вернулся — выбор на месте", sel(at) == ["08455000", "08455001"])
at = page(**{"pp-type": "battery", "pp-sku": "99601000-B"})
check("ключ списка несёт тип: смена типа пересоздаёт список (правило 7б)",
      picker(at).key == "pp-pick-battery-99601000-B")
check("товар карточки вне фильтра — карточка на месте, список честно говорит, что он вне типа",
      not at.exception and t("pp.type.ctx_outside", sku="99601000-B", ty=t("tg.type.battery")) in texts_of(at)
      and any("pp-photo" in str(m.value) for m in at.markdown))

at = page(**{"pp-sku": "NOPE-0001"})
check("Реестр, «Любой», товар вне списка — прежняя подпись про тип, а не «очистите поиск» генератора",
      t("pp.type.ctx_outside", sku="NOPE-0001", ty=pa.type_label("any")) in texts_of(at)
      and t("pp.pick.ctx_outside_q", sku="NOPE-0001") not in texts_of(at))

print("массовых действий нет")
keys = {str(b.key) for b in page(**{"pp-type": "grinder"}).button}
check("у выбора только «Выбрать все» и «Очистить»: ни генерации, ни принятия, ни отправки",
      {k for k in keys if k.startswith("pp-multi")} == {"pp-multi-all", "pp-multi-clear"})

print()
print(f"ИТОГ: {'всё ок' if not FAILS else f'провалов {len(FAILS)}'}")
sys.exit(1 if FAILS else 0)
