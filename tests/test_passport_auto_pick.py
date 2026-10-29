# -*- coding: utf-8 -*-
"""
tests/test_passport_auto_pick.py — выбор товара в разделе «Паспорт SKU»
(поручение владельца 29.10.2026).

Что заперто:
  · выбор из Реестра живёт при переходе по вкладкам («Создание Паспорта»,
    «Взаимодействие с Верификатором») и на страницу генератора и обратно;
  · выбора нет вовсе и в Реестре ровно один товар с паспортом — он выбран
    автоматически, с подписью; выбор можно сменить в Реестре;
  · товаров с паспортом больше одного — прежняя подсказка и «Перейти в Реестр»;
  · одна строка после поиска или фильтра — не повод: поиск ничего не выбирает;
  · сделанный человеком выбор (в том числе явный сброс) автовыбор не перебивает;
  · автовыбор ничего не создаёт: у 99601000-B (паспорт v2) — существующий паспорт,
    второго нет, «Создать Паспорт» не предлагается;
  · Реестр не прочитался — автовыбора нет.

Запуск (pytest не нужен):  python tests/test_passport_auto_pick.py
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




def passport_docx(sku: str, ver: str = "2", state: str = "NOT_READY") -> bytes:
    body = (_p(f"Паспорт SKU {sku}", "Title")
            + _tbl([("Параметр", "Значення"), ("passport_id", f"PASS-{sku}-001"), ("passport_version", ver),
                    ("state", state), ("sku_id", sku)]))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                   f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    return b.getvalue()


# два паспорта различаются состоянием и типом: каждый фильтр Реестра оставляет одну строку
DOCS = {"99601000-B": passport_docx("99601000-B"), "21680000": passport_docx("21680000", "1", "READY")}
TS = pd.Timestamp("2026-10-21 18:05", tz="UTC")


def copy_row(sku: str) -> dict:
    return dict(source_artifact_id=f"DOCX-PASS-{sku}-001-v1", sku_id=sku, passport_id=f"PASS-{sku}-001",
                archived_locator=f"/Volumes/x/{sku}.docx", sha256=hashlib.sha256(DOCS[sku]).hexdigest(),
                bytes=len(DOCS[sku]), lifecycle="ACTIVE", registered_by="a", recorded_at=TS)


COPY = pd.DataFrame([copy_row("99601000-B")])
DIRECTORY = pd.DataFrame([
    dict(sku="99601000-B", name="Пилосос садовий DVB-200BC Dual", ean="", is_active=True, asins="B0GTRY26HB"),
    dict(sku="21680000", name="Насос поверхностный PW-14B", ean="", is_active=True, asins=""),
    dict(sku="55550000", name="Акумулятор BP-240", ean="", is_active=True, asins=""),
])
LISTING = pd.DataFrame([dict(asin="B0PUMP0001", sku_group="21680000", title="Bomba de superficie Dnipro-M PW-14B 1100W",
                               product_type=None, mp="es", competitor=False)])
FAILED_TITLE = {}
MODE = {"dir_fail": False, "listing_fail": False, "reg_fail": False}

def fake_sql(sql, con=None, params=None, **kw):
    q = " ".join(str(sql).split())
    if "to_regclass" in q:
        return pd.DataFrame([{"t": (params or {}).get("n", "")}])
    if "FROM passport_source_artifacts" in q:
        return COPY.copy()
    if "FROM passport_blocks" in q and MODE["reg_fail"]:
        # сбой другого запроса Реестра: единственная копия при этом видна — и всё равно
        # «один» по неполному Реестру не утверждается
        raise RuntimeError("реестр недоступен")
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

pc.volume_store = lambda: type("S", (), {"get": lambda self, loc: DOCS[loc.rsplit("/", 1)[1][:-5]]})()
from services import product_specs as ps  # noqa: E402

ps.load = lambda asin, mp: (None, "нет снапшота в тесте")
import services.passport as pp  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from i18n import t  # noqa: E402

from services import textgen as tg  # noqa: E402

CONTENT, TEXTGEN = "pages/content.py", "pages/textgen.py"
# генератор: учёт лимитов и последнее предложение — из журнала, здесь не проверяются
tg.usage_now = lambda sku: (tg.Usage(), None)
tg.latest = lambda sku, mp: (pd.DataFrame(), None)
# ключи по типу — не предмет этого теста (их подмена — test_textgen_page.py)
ps.same_type_asins = lambda tool_type, mp: ([], None)


def app(**state):
    st.cache_data.clear()
    st.cache_resource.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.switch_page(CONTENT)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def ctx(at):
    return at.session_state["pp-sku"] if "pp-sku" in at.session_state else None


def texts_of(at) -> str:
    out = []
    for coll in (at.markdown, at.caption, at.info, at.warning, at.error, at.success):
        out += [str(x.value) for x in coll]
    return "\n".join(out)


def picker(at):
    return next((s for s in at.selectbox if str(s.key).startswith("pp-pick-")), None)


def tab(at, name):
    at.session_state["pp-tab"] = name
    return at.run()


print("выбор живёт при переходе по вкладкам и страницам")
at = app(**{"pp-tab": "registry"})
picker(at).set_value("21680000").run()
check("выбор в Реестре — контекст", ctx(at) == "21680000")
tab(at, "create")
check("«Создание Паспорта» — на том же SKU", ctx(at) == "21680000" and "21680000" in texts_of(at)
      and t("pp.create_pick") not in texts_of(at))
tab(at, "verifier")
check("«Взаимодействие с Верификатором» — на том же SKU",
      any('class="ls-mono"' in str(m.value) and "21680000" in str(m.value) for m in at.markdown))
at.switch_page(TEXTGEN).run()
check("генератор — на том же SKU (общий выбор)", not at.exception and picker(at) is not None
      and picker(at).value == "21680000")
at.switch_page(CONTENT).run()
tab(at, "create")
check("вернулись в «Паспорт SKU» — выбор тот же", ctx(at) == "21680000" and t("pp.create_pick") not in texts_of(at))
at.switch_page(TEXTGEN).run()
picker(at).set_value("99601000-B").run()
check("генератор на 99601000-B открывается без исключения", not at.exception)
at.switch_page(CONTENT).run()
tab(at, "create")
check("выбор на генераторе — в «Паспорт SKU» он же (в обе стороны)", ctx(at) == "99601000-B")

print("автовыбор: в Реестре ровно один товар с паспортом")
at = app(**{"pp-tab": "create"})
check("выбора не было — выбран единственный товар с паспортом (99601000-B)", ctx(at) == "99601000-B")
check("подпись «Выбран автоматически…» видна, подсказки «выберите товар» нет",
      t("pp.auto_picked") in texts_of(at) and t("pp.create_pick") not in texts_of(at)
      and not any(b.key == "pp-to-reg" for b in at.button))
check("автовыбор ничего не создаёт: у 99601000-B — существующий паспорт, «Создать Паспорт» не предлагается",
      t("pp.create_copy", aid="DOCX-PASS-99601000-B-001-v1", ver="2", state=t("pp.state.NOT_READY")) in texts_of(at)
      and not any(b.key == "pp-create-off" for b in at.button)
      and all(b.disabled for b in at.button if b.key in ("pp-delta-off", "pp-recreate-off")))
check("и не пишет: поколение выбора не тронуто (это не выбор человека)",
      ("pp-sku-gen" not in at.session_state) or at.session_state["pp-sku-gen"] == 0)
tab(at, "verifier")
check("«Взаимодействие с Верификатором» — на нём же",
      any('class="ls-mono"' in str(m.value) and "99601000-B" in str(m.value) for m in at.markdown))
tab(at, "registry")
picker(at).set_value("21680000").run()
check("выбор можно сменить в Реестре — подпись автовыбора уходит",
      ctx(at) == "21680000" and t("pp.auto_picked") not in texts_of(at))
picker(at).set_value("99601000-B").run()
tab(at, "create")
check("человек снова выбрал тот же товар — это его выбор: подписи «автоматически» нет",
      ctx(at) == "99601000-B" and t("pp.auto_picked") not in texts_of(at))
at = app(**{"pp-tab": "verifier"})
check("автовыбор и на «Взаимодействии с Верификатором» (сразу, без «Создания»), с подписью",
      ctx(at) == "99601000-B" and t("pp.auto_picked") in texts_of(at))

at = app(**{"pp-tab": "registry"})
check("Реестр открывается без автовыбора — список пуст, как раньше (#178)",
      ctx(at) is None and picker(at) is not None and picker(at).value == "")

print("не перебивать выбор человека")
at = app(**{"pp-tab": "registry"})
picker(at).set_value("21680000").run()
picker(at).set_value("").run()
check("выбрал и сбросил в списке — это выбор человека: товара нет", ctx(at) is None)
tab(at, "create")
check("и на «Создании» — прежняя подсказка, без автовыбора",
      ctx(at) is None and t("pp.create_pick") in texts_of(at) and any(b.key == "pp-to-reg" for b in at.button))
at = app(**{"pp-tab": "create", "pp-sku": "21680000"})
check("выбор уже есть — автовыбор его не меняет", ctx(at) == "21680000" and t("pp.auto_picked") not in texts_of(at))

print("несколько паспортов — автовыбора нет")
COPY = pd.DataFrame([copy_row("99601000-B"), copy_row("21680000")])
at = app(**{"pp-tab": "create"})
check("два товара с паспортом — прежняя подсказка и «Перейти в Реестр»",
      ctx(at) is None and t("pp.create_pick") in texts_of(at) and any(b.key == "pp-to-reg" for b in at.button))
# поиск и фильтр оставляют в Реестре одну строку — и всё равно на «Создании» выбора нет:
# «один» считается по всем паспортам Реестра, а не по строкам под поиском
at = app(**{"pp-tab": "registry", "pp-q": "99601000"})
tab(at, "create")
check("одна строка после поиска — не повод: поиск ничего не выбирает", ctx(at) is None
      and t("pp.create_pick") in texts_of(at))
def table_skus(at):
    return next((list(d.value["sku"]) for d in at.dataframe if "next" in getattr(d.value, "columns", [])), [])


for flt, label in (({"pp-type": "unknown"}, "фильтр типа"), ({"pp-states": ["READY"]}, "фильтр состояния")):
    at = app(**{"pp-tab": "registry", **flt})
    rows = table_skus(at)
    tab(at, "create")
    check(f"{label} оставил в Реестре одну строку с паспортом ({rows}) — не повод: на «Создании» выбора нет",
          len(rows) == 1 and ctx(at) is None and t("pp.create_pick") in texts_of(at))
COPY = pd.DataFrame([copy_row("99601000-B")])

print("Реестр не прочитался — автовыбора нет")
MODE["reg_fail"] = True
at = app(**{"pp-tab": "create"})
check("сбой чтения паспортов — «один» не утверждается, выбора нет", not at.exception and ctx(at) is None)
MODE["reg_fail"] = False
# Сейчас при сбое или без миграции Реестр отдаёт пустой список паспортов; охрана — на
# случай, если он начнёт отдавать частичный: ошибка + один паспорт — всё равно не «один».
_lr = pp.load_registry
for _bad in ({"error": "OperationalError: x"}, {"missing": True}):
    pp.load_registry = lambda _b=_bad: {"objects": pd.DataFrame([{"sku_id": "99601000-B"}]), "error": None,
                                        "missing": False, **_b}
    at = app(**{"pp-tab": "create"})
    check(f"Реестр с {'ошибкой' if 'error' in _bad else 'без миграции'} и одним паспортом — автовыбора нет",
          ctx(at) is None)
pp.load_registry = _lr

print()
print(f"ИТОГ: {'всё ок' if not FAILS else f'провалов {len(FAILS)}'}")
sys.exit(1 if FAILS else 0)
