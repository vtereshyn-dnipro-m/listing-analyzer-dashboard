# -*- coding: utf-8 -*-
"""
tests/test_passport_card_photo.py — фото товара в карточке Реестра Паспортов
(поручение владельца 28.10.2026). Без сети: базы Listing Suite и Кабинета подменены.

Что заперто:
  · фото — из последнего (по времени) УДАЧНОГО снапшота НАШЕГО листинга ES, первая
    картинка этого ASIN (`images_of_specified_asin`); запасной `main_image` нет — она
    бывает картинкой другой вариации (проверка #180);
  · ASIN, который справочник даёт и другому SKU, — заглушка с причиной;
  · SKU связан с листингом только по ASIN справочника Кабинета, не по sku_group
    матрицы: у B0GTRY26HB группа «99601000», а продаётся набор 99601000-B;
  · несколько ASIN с фото — заглушка, не угадываем; конкурент и не ES — не источник;
  · пустая, NaN и не-амазоновская ссылка — заглушка «фото отсутствует», без падения;
  · сбой чтения — заглушка и причина на экране;
  · карточка: фото рядом с названием одной строкой HTML (правило 1), рамка фиксирована,
    alt пустой — незагрузившаяся ссылка не рисует битую картинку;
  · примеры владельца: 08087000 (тип не определён, паспорта нет) и 99601000-B
    (паспорт v2 «В работе») — карточка без ошибки.

Запуск (pytest не нужен):  python tests/test_passport_card_photo.py
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

IMG = "https://m.media-amazon.com/images/I/71d8pY+UJkL._AC_SL1500_.jpg"
MAIN = "https://m.media-amazon.com/images/I/71d8pY+UJkL._AC_SY300_SX300_QL70_ML2_.jpg"
OTHER = "https://m.media-amazon.com/images/I/51OTHERxx1L._AC_SL1500_.jpg"
OLD = "https://m.media-amazon.com/images/I/41OLDxxxx1L._AC_SL1500_.jpg"
IMG2 = "https://m.media-amazon.com/images/I/61SHARExx1L._AC_SL1500_.jpg"
IMG3 = "https://m.media-amazon.com/images/I/61OWNxxxx1L._AC_SL1500_.jpg"

DIRECTORY = pd.DataFrame([
    dict(sku="99601000-B", name="Dnipro-M Cordless Leaf Blower and Vacuum DVB-200BC Dual", ean="", is_active=True,
         asins="B0GTRY26HB"),
    dict(sku="08087000", name="Pistola de calor Dnipro-M GH-201N", ean="", is_active=True, asins="B0HEAT0001"),
    dict(sku="11110000", name="Битая ссылка", ean="", is_active=True, asins="B0BAD00001"),
    dict(sku="22220000", name="Без фото ASIN, но с main_image", ean="", is_active=True, asins="B0MAIN0001"),
    # один ASIN у двух SKU (набор и голый инструмент) — чьё фото, не знаем
    dict(sku="88880001", name="Набор", ean="", is_active=True, asins="B0SHARE001"),
    dict(sku="88880002", name="Инструмент без набора", ean="", is_active=True, asins="B0SHARE001"),
    # у SKU свой ASIN и ASIN, общий с другим SKU: фото — по своему
    dict(sku="88880003", name="Свой и общий ASIN", ean="", is_active=True, asins="B0OWN00001 B0SHARE002"),
    dict(sku="88880004", name="Второй владелец общего", ean="", is_active=True, asins="B0SHARE002"),
    dict(sku="33330000", name="Два ASIN с фото", ean="", is_active=True, asins="B0TWO00001 B0TWO00002"),
    # ASIN справочника в матрице ES нет, а точный sku_group есть у чужого ASIN
    dict(sku="44440000", name="Только группа в матрице", ean="", is_active=True, asins="B0NOTINMX1"),
    dict(sku="55550000", name="Конкурент и не ES", ean="", is_active=True, asins="B0COMP0001 B0DE000001"),
    dict(sku="66660000", name="Пустые ссылки", ean="", is_active=True, asins="B0EMPTY001"),
])
COPY = pd.DataFrame([dict(source_artifact_id="DOCX-PASS-99601000-B-001-v2", sku_id="99601000-B",
                          passport_id="PASS-99601000-B-001", archived_locator=LOC, sha256=SHA, bytes=len(DOCX),
                          lifecycle="ACTIVE", registered_by="a", recorded_at=TS)])
NA = float("nan")
# Снапшоты: asin, рынок, конкурент, sku_group матрицы, удачный ли, время, images_of_specified_asin[0], main_image
SNAPS = pd.DataFrame([
    dict(asin="B0GTRY26HB", mp="es", competitor=False, grp="99601000", ok=True, at=3, spec=IMG, main=MAIN),
    # ловушка: старый удачный снапшот с прежней картинкой — без «ORDER BY … DESC» фото было бы старым
    dict(asin="B0GTRY26HB", mp="es", competitor=False, grp="99601000", ok=True, at=1, spec=OLD, main=OLD),
    # ловушка: самый свежий НЕудачный снапшот с чужой картинкой — без «s.ok IS TRUE» фото было бы чужим
    dict(asin="B0GTRY26HB", mp="es", competitor=False, grp="99601000", ok=False, at=4, spec=OTHER, main=OTHER),
    dict(asin="B0SHARE001", mp="es", competitor=False, grp="88880001", ok=True, at=1, spec=IMG2, main=IMG2),
    dict(asin="B0OWN00001", mp="es", competitor=False, grp="88880003", ok=True, at=1, spec=IMG3, main=IMG3),
    dict(asin="B0SHARE002", mp="es", competitor=False, grp="88880003", ok=True, at=1, spec=OTHER, main=OTHER),
    dict(asin="B0BAD00001", mp="es", competitor=False, grp="11110000", ok=True, at=1, spec="javascript:alert(1)",
         main="https://example.com/x.jpg\" onerror=\"alert(1)"),
    dict(asin="B0MAIN0001", mp="es", competitor=False, grp="22220000", ok=True, at=1, spec=NA, main=MAIN),
    dict(asin="B0TWO00001", mp="es", competitor=False, grp="33330000", ok=True, at=1, spec=IMG, main=MAIN),
    dict(asin="B0TWO00002", mp="es", competitor=False, grp="33330000", ok=True, at=1, spec=OTHER, main=OTHER),
    # ловушка: точный sku_group, но ASIN не из справочника — фото по группе было бы чужим
    dict(asin="B0GROUP001", mp="es", competitor=False, grp="44440000", ok=True, at=1, spec=OTHER, main=OTHER),
    dict(asin="B0COMP0001", mp="es", competitor=True, grp="55550000", ok=True, at=1, spec=OTHER, main=OTHER),
    dict(asin="B0DE000001", mp="de", competitor=False, grp="55550000", ok=True, at=1, spec=OTHER, main=OTHER),
    dict(asin="B0EMPTY001", mp="es", competitor=False, grp="66660000", ok=True, at=1, spec="", main=None),
])
MODE = {"dir_fail": False, "photo_fail": False}
SEEN = []


def fake_sql(sql, con=None, params=None, **kw):
    q = " ".join(str(sql).split())
    if "to_regclass" in q:
        return pd.DataFrame([{"t": (params or {}).get("n", "")}])
    if "FROM passport_source_artifacts" in q:
        return COPY.copy()
    if "images_of_specified_asin" in q:
        SEEN.append(q)
        if MODE["photo_fail"]:
            raise RuntimeError("снапшоты недоступны")
        df = SNAPS.copy()
        if "pm.marketplace = 'es'" in q:
            df = df[df["mp"] == "es"]
        if "pm.is_competitor IS NOT TRUE" in q:
            df = df[~df["competitor"]]
        if "s.ok IS TRUE" in q:
            df = df[df["ok"]]
        # LIMIT 1 после ORDER BY: свежий снапшот только при «ORDER BY s.fetched_at DESC»
        df = df.sort_values("at", ascending="ORDER BY s.fetched_at DESC" not in q, kind="stable")
        # без условия по ASIN справочника в выборку идёт вся матрица — и чужие ASIN группы;
        # условие по sku_group база тоже исполнила бы: строки группы добавляются, как в базе
        if "pm.asin = ANY(%(a)s)" in q:
            keep = df["asin"].isin((params or {}).get("a", []))
            if "pm.sku_group" in q:
                vals = [v for v in (params or {}).values() if isinstance(v, str)]
                vals += [x for v in (params or {}).values() if isinstance(v, list) for x in v]
                keep |= df["grp"].isin(vals)
            df = df[keep]
        df = df.drop_duplicates("asin")
        return df[["asin", "spec"] + (["main"] if "AS main" in q else [])].reset_index(drop=True)
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


def photo(sku):
    st.cache_data.clear()
    return pp.sku_photo(sku)


# ================================================================ сервис
print("источник фото")
p = photo("99601000-B")
check("99601000-B: фото из удачного снапшота нашего ES-листинга, картинка этого ASIN",
      p["url"] == IMG and p["asin"] == "B0GTRY26HB" and p["why"] is None)
# Фейк не исполняет SQL, поэтому условие выборки заперто целиком: любое добавленное
# «OR …» (по sku_group, по названию) дало бы фото другого товара (проверка #180).
check("запрос фото: внешнее условие ровно «ES, наш листинг, ASIN справочника», без sku_group",
      bool(SEEN) and SEEN[-1].split(") ph ON true ", 1)[-1]
      == "WHERE pm.marketplace = 'es' AND pm.is_competitor IS NOT TRUE AND pm.asin = ANY(%(a)s)"
      and "sku_group" not in SEEN[-1])
check("запрос фото: снапшот того же ASIN и рынка, удачный, самый свежий",
      "WHERE s.asin = pm.asin AND s.marketplace = pm.marketplace AND s.ok IS TRUE "
      "ORDER BY s.fetched_at DESC LIMIT 1" in SEEN[-1])
p = photo("08087000")
check("08087000: нашего листинга ES нет — фото нет, причина no_listing", p["url"] is None and p["why"] == "no_listing")
check("NaN в images_of_specified_asin — заглушка: main_image не запасная, она бывает картинкой другой "
      "вариации (проверка #180)", photo("22220000") == {"url": None, "asin": None, "why": "bad_url", "err": None})
check("берётся самый свежий удачный снапшот, а не старый", photo("99601000-B")["url"] == IMG)
p = photo("88880001")
check("ASIN у двух SKU справочника — заглушка у обоих, причина shared с ASIN и вторым SKU",
      p["url"] is None and p["why"] == "shared" and "B0SHARE001" in p["err"] and "88880002" in p["err"]
      and photo("88880002")["why"] == "shared")
p = photo("88880003")
check("свой ASIN и общий с другим SKU — фото по своему, общий не мешает",
      p["url"] == IMG3 and p["asin"] == "B0OWN00001")
p = photo("33330000")
check("два ASIN с фото — не угадываем, причина several со списком ASIN",
      p["url"] is None and p["why"] == "several" and "B0TWO00001" in p["err"] and "B0TWO00002" in p["err"])
p = photo("44440000")
check("ASIN справочника в матрице ES нет, точный sku_group есть у чужого ASIN — фото нет (группа ≠ точный SKU)",
      p["url"] is None and p["why"] == "no_listing")
check("конкурент и листинг не ES — не источник фото", photo("55550000")["url"] is None)
check("ссылка не на картинку Amazon (javascript:, чужой домен с кавычкой) — не фото, причина bad_url",
      photo("11110000") == {"url": None, "asin": None, "why": "bad_url", "err": None})
check("пустая и NULL ссылка — не фото, причина bad_url", photo("66660000")["why"] == "bad_url")
check("SKU нет в справочнике — фото нет, без падения", photo("00000000")["why"] == "no_listing")
check("photo_url: NaN, None, пусто, http, чужой домен — None; картинка Amazon — сама ссылка",
      [pp.photo_url(x) for x in (NA, None, "", "http://m.media-amazon.com/images/I/a.jpg",
                                 "https://evil.example/images/I/a.jpg", IMG)] == [None] * 5 + [IMG])
MODE["photo_fail"] = True
p = photo("99601000-B")
check("снапшоты не прочитались — фото нет, причина error с текстом", p["why"] == "error" and "недоступны" in p["err"])
MODE["photo_fail"] = False
check("сбой не кэшируется: база вернулась — фото сразу", pp.sku_photo("99601000-B")["url"] == IMG)
MODE["dir_fail"] = True
p = photo("99601000-B")
check("справочник Кабинета не прочитался — фото нет, причина error", p["url"] is None and p["why"] == "error")
MODE["dir_fail"] = False

print("разметка фото")
h = pa.photo_html({"url": IMG, "asin": "B0GTRY26HB"})
check("фото: картинка по ссылке, alt пустой (битая ссылка не рисует значок), ленивая загрузка",
      f'src="{IMG}"' in h and 'alt=""' in h and 'loading="lazy"' in h and t("pp.photo.none") not in h)
check("рамка фото фиксированного размера — медленная загрузка не двигает карточку",
      "width:88px;height:88px" in h and "object-fit:contain" in h)
n = pa.photo_html({"url": None, "why": "no_listing"})
check("нет фото — заглушка «фото отсутствует», картинки нет, причина во всплывающей подсказке",
      t("pp.photo.none") in n and "<img" not in n and 'title="' in n)
check("разметка одной строкой (правило 1)", "\n" not in h and "\n" not in n)

# ================================================================ карточка (AppTest)
print("карточка в Реестре")


def page(**state):
    st.cache_data.clear()
    st.cache_resource.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.switch_page("pages/content.py")
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def picker(at):
    return next((s for s in at.selectbox if str(s.key).startswith("pp-pick-")), None)


def card(at):
    return next((str(m.value) for m in at.markdown if "pp-photo" in str(m.value)), "")


at = page(**{"pp-tab": "registry"})
picker(at).set_value("99601000-B").run()
c = card(at)
check("99601000-B (паспорт v2 «В работе»): карточка с фото рядом с названием, без ошибки",
      not at.exception and f'src="{IMG}"' in c and "DVB-200BC" in c and t("pp.photo.none") not in c
      and c.index("pp-photo") < c.index("DVB-200BC"))
check("99601000-B: статус паспорта в карточке тот же — «В работе», v2",
      t("pp.state.NOT_READY") in c and t("pp.ver_short", v="2") in c)
check("99601000-B: кнопки карточки на месте", any(b.key in ("pp-act", "pp-open") for b in at.button))
check("карточка одной строкой HTML (правило 1)", "\n" not in c)

picker(at).set_value("08087000").run()
c = card(at)
check("08087000 (тип не определён, паспорта нет): карточка с заглушкой «фото отсутствует», без ошибки",
      not at.exception and t("pp.photo.none") in c and "<img" not in c and "GH-201N" in c)
check("08087000: кнопка «Создать Паспорт» на месте", any(b.key == "pp-act" for b in at.button))

for sku in ("11110000", "66660000", "33330000", "88880001"):
    picker(at).set_value(sku).run()
    c = card(at)
    check(f"{sku}: битая, пустая или неоднозначная ссылка — заглушка, без картинки и без ошибки",
          not at.exception and t("pp.photo.none") in c and "<img" not in c)

MODE["photo_fail"] = True
at = page(**{"pp-tab": "registry", "pp-sku": "99601000-B"})
check("снапшоты не прочитались — карточка работает, заглушка и причина подписью на экране (не только в подсказке)",
      not at.exception and t("pp.photo.none") in card(at)
      and any(t("pp.photo.why.error", err="RuntimeError: снапшоты недоступны") in str(c.value) for c in at.caption))
MODE["photo_fail"] = False

print("фото в таблице массового выбора")
SKUS = list(DIRECTORY["sku"])
st.cache_data.clear()
n0 = len(SEEN)
batch = pp.sku_photos(SKUS)
check("пакет — один запрос снапшотов на весь выбор", len(SEEN) - n0 == 1)
check("пакет даёт по каждому SKU ровно то же, что карточка (sku_photo)",
      all(batch[s] == photo(s) for s in SKUS))
MODE["photo_fail"] = True
st.cache_data.clear()
check("сбой снапшотов в пакете — у SKU с ASIN причина error, без ASIN — no_listing",
      pp.sku_photos(["99601000-B", "00000000"]) == {
          "99601000-B": {"url": None, "asin": None, "why": "error", "err": "RuntimeError: снапшоты недоступны"},
          "00000000": {"url": None, "asin": None, "why": "no_listing", "err": None}})
MODE["photo_fail"] = False
at = page(**{"pp-tab": "registry", "pp-type": "unknown"})
want = ["99601000-B", "08087000", "33330000", "88880001", "88880003"]
n0 = len(SEEN)
next(m for m in at.multiselect if str(m.key).startswith("pp-multi-w-")).set_value(want).run()
check("на странице фото всего выбора — одним запросом, а не по запросу на товар", len(SEEN) - n0 == 1)
tbl = next((d.value for d in at.dataframe if "img" in getattr(d.value, "columns", [])), None)
got = dict(zip(tbl["sku"], tbl["img"])) if tbl is not None else {}
check("в таблице выбранных — колонка фото: у 99601000-B фото его ASIN, у своего ASIN рядом с общим — своё",
      not at.exception and got.get("99601000-B") == IMG and got.get("88880003") == IMG3)
# пустая ячейка в строковом столбце pandas 3 — NaN (null в Arrow, Streamlit рисует пусто): правило 4
check("нет фото (нет листинга ES, два ASIN, ASIN у двух SKU) — пустая ячейка, не чужое фото",
      all(s in got and pd.isna(got[s]) for s in ("08087000", "33330000", "88880001")))
check("SKU без фото названы подписью под таблицей",
      any(t("pp.multi.no_photo", n=3, skus="08087000, 33330000, 88880001") in str(c.value) for c in at.caption))

print()
print(f"ИТОГ: {'всё ок' if not FAILS else f'провалов {len(FAILS)}'}")
sys.exit(1 if FAILS else 0)
