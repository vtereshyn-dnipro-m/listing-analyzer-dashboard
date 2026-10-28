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
         product_type="LEAF_BLOWER"),
    dict(asin="B0PUMP0001", sku_group="21680000", title="Bomba de superficie Dnipro-M PW-14B 1100W", product_type=None),
    dict(asin="B0BAT00001", sku_group="", title="Batería de litio Dnipro-M BP-240 20V 4Ah", product_type="BATTERY"),
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
    if q.startswith("SELECT asin, sku_group FROM product_matrix WHERE marketplace"):
        return LISTING[["asin", "sku_group"]].copy()
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
check("листинги ES прочитаны, тип узнан по тайтлу и productType", lerr is None
      and dict(zip(listing["asin"], listing["type"])) == {"B0GTRY26HB": "blower", "B0PUMP0001": "pump",
                                                          "B0BAT00001": "battery"})
check("SKU → тип: по ASIN справочника (99601000-B, 55550000) и по точному sku_group (21680000)",
      types == {"99601000-B": "blower", "21680000": "pump", "55550000": "battery"})
check("у SKU без листинга ES типа нет — не выдумывается", "77770000" not in types)
mixed = pd.DataFrame([dict(asin="A1", sku_group="X", type="drill"), dict(asin="A2", sku_group="X", type="hammer"),
                      dict(asin="A3", sku_group="X", type="hammer")])
check("разные типы у одного SKU — самый частый, стабильно",
      pp.sku_types(pd.DataFrame([dict(sku="X", asins="")]), mixed) == {"X": "hammer"})
MODE["listing_fail"] = True
st.cache_data.clear()
_l, _e = pp.listing_types_es()
check("листинги не прочитались — причина, а не пустота «типов нет»", _e is not None and _l.empty)
MODE["listing_fail"] = False
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
GEN_SRC = (ROOT / "services" / "textgen.py").read_text(encoding="utf-8")
check("генерация передаёт тип в проверки и в промпт",
      "kind=kind_of(tool_type))" in GEN_SRC and "build_prompt(sku, marketplace, header, facts, tool_type)" in GEN_SRC)
AREA = (ROOT / "components" / "passport_area.py").read_text(encoding="utf-8")
check("выделение строки таблицы применяется только при смене — не перебивает выбор из списка",
      'if sel and sel != st.session_state.get("pp-table-last"):' in AREA)


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
check("«Верификатор» на том же SKU: у товара без копии блока конфликтов нет",
      not any(str(b.key).startswith("pp-cfd-save-") for b in at.button) and not at.exception)

at = page(**{"pp-tab": "registry"})
picker(at).set_value("21680000").run()
at.session_state["pp-sku"] = "99601000-B"           # выбор в другом месте (строка Реестра, «Сменить товар»)
at.run()
check("SKU выбран в другом месте — список стоит на нём, прежний выбор не возвращается (правило 7б)",
      picker(at) is not None and picker(at).value == "99601000-B" and ctx(at) == "99601000-B")

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
