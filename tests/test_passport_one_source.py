# -*- coding: utf-8 -*-
"""
tests/test_passport_one_source.py — один паспорт на SKU для раздела «Паспорт
SKU» и генератора (решение владельца 28.10.2026), чеклист пунктов 1–7.

Живой случай: у 99601000-B есть действующая копия v2 в томе UC, генератор
по ней работает, а раздел говорил «Паспорт отсутствует» — он читал только
`passport_objects` (0 строк). Что заперто:

  · (2) Реестр видит копию: у SKU есть паспорт, состояние из шапки копии,
    свежесть подтверждена; «Создать Паспорт» не предлагается — второго
    паспорта на SKU нет; если у SKU есть строка `passport_objects`, главнее она;
  · (4) поиск по SKU, названию, модели (из копии), ASIN и EAN находит его;
  · (3) на «Создании» — тот же блок загрузки docx, что в генераторе;
  · (1) «Собрано по SKU»: название, EAN, ASIN, ASIN ES, тип, модель,
    характеристики с источником и текущий тайтл — без ручного ввода;
  · (6) в карточке паспорта — комплектация с количествами и конфликты со
    статусом и источником решения;
  · (7) верификатор закрывает конфликт: решение с источником пишется одной
    строкой, поля пересоздаются (правило 7б); без источника — отказ, без
    права — кнопка выключена, без миграции — выключена и названа миграция.

Без сети: базы Listing Suite и Кабинета, том и снапшот подменены.

Запуск (pytest не нужен):  python tests/test_passport_one_source.py
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
        + _tbl([("Поле", "Значення", "Статус", "Джерело"), ("Назва", "Садовий пилосос DVB-200BC Dual", "P", "S"),
                ("Модель", "DVB-200BC Dual", "PROPOSED", "SRC-1")])
        + _p("Комплектація та функціональні елементи", "Heading1")
        + _tbl([("ID", "Елемент", "Кількість", "Статус", "Джерело"),
                ("KIT-99601000-B-006", "Колеса", "1", "PROPOSED/UNVERIFIED", "SRC-3"),
                ("KIT-99601000-B-010", "Акумулятор BP-240 4 Ah", "2", "PROPOSED/UNVERIFIED", "SRC-5")])
        + _p("Конфлікти", "Heading1")
        + _tbl([("ID", "Поле", "Сторона A", "Сторона B", "Статус"),
                ("CONFLICT-99601000-B-002", "Комплектація АКБ і ЗП", "UA: без АКБ та ЗП",
                 "Marketplace: 2× BP-240 4 Ah + FC-230 Dual", "OPEN_OWNER_DECISION"),
                ("CONFLICT-99601000-B-005", "Гарантія", "36 months", "5 years", "RESOLVED_MARKET_SCOPE"),
                ("CONFLICT-99601000-B-007", "Автономність", "до 39 хв *ManoMano*", "$5 [x]", "OPEN_EVIDENCE")]))
_b = io.BytesIO()
with zipfile.ZipFile(_b, "w") as z:
    z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
               f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
DOCX = _b.getvalue()
SHA = hashlib.sha256(DOCX).hexdigest()
AID = "DOCX-PASS-99601000-B-001-v2"
LOC = "/Volumes/dnipro_m/listing_data/passports/99601000-B/PASS-99601000-B-001/v2/PASS-99601000-B-001_v2.docx"
TS = pd.Timestamp("2026-10-21 18:05", tz="UTC")

DIRECTORY = pd.DataFrame([
    dict(sku="99601000-B", name="Пилосос садовий DVB-200BC Dual + 2 АКБ", ean="4823102367354", is_active=True,
         asins="B0GTRY26HB"),
    dict(sku="21680000", name="Насос поверхностный PW-14B", ean="4823102300001", is_active=True, asins=""),
])
COPY = pd.DataFrame([dict(source_artifact_id=AID, sku_id="99601000-B", passport_id="PASS-99601000-B-001",
                          archived_locator=LOC, sha256=SHA, bytes=len(DOCX), lifecycle="ACTIVE",
                          registered_by="agent:v.tereshyn@dniprom.com", recorded_at=TS),
                     # прежняя копия: в Реестр не идёт (проверка #176), в списке копий — есть
                     dict(source_artifact_id="DOCX-PASS-99601000-B-001-v1", sku_id="99601000-B",
                          passport_id="PASS-99601000-B-001", archived_locator=LOC.replace("/v2/", "/v1/"),
                          sha256="d" * 64, bytes=1, lifecycle="OLD", registered_by="a", recorded_at=TS)])
OBJ_COLS = ["passport_id", "lineage_id", "sku_id", "product_version", "product_name", "model", "state",
            "passport_version", "sha256", "storage_path", "materials_url", "limitations", "last_event_type",
            "last_event_at", "readback_sha256", "readback_at"]
DEC: list[dict] = []
MODE = {"no_decisions_table": False, "objects": pd.DataFrame(columns=OBJ_COLS)}
DEC_COLS = ["id", "conflict_id", "decision", "value", "decision_source", "decided_by", "decided_at"]


def fake_sql(sql, con=None, params=None, **kw):
    q = " ".join(str(sql).split())
    if "to_regclass" in q:
        name = (params or {}).get("n", "")
        return pd.DataFrame([{"t": None if (MODE["no_decisions_table"] and "conflict_decisions" in name) else name}])
    if "FROM passport_objects" in q:
        return MODE["objects"].copy()
    if "FROM passport_source_artifacts" in q:
        return COPY[COPY["lifecycle"] == "ACTIVE"].copy() if "lifecycle = 'ACTIVE'" in q else COPY.copy()
    if "FROM passport_conflict_decisions" in q:
        rows = [d for d in DEC if (d["source_artifact_id"], d["artifact_sha256"]) == (params["a"], params["s"])]
        return pd.DataFrame([{k: d[k] for k in DEC_COLS} for d in rows], columns=DEC_COLS)
    if q.startswith("SELECT asin, sku_group FROM product_matrix WHERE marketplace"):
        if MODE.get("matrix_fail"):
            raise RuntimeError("матрица недоступна")
        return pd.DataFrame([{"asin": "B0GTRY26HB", "sku_group": "99601000"}])
    return pd.DataFrame()


pd.read_sql = fake_sql


class WConn:
    """База для записи решения: INSERT ложится в DEC, как настоящая строка."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self

    def execute(self, sql, p=()):
        assert sql.startswith("INSERT INTO passport_conflict_decisions"), sql
        DEC.append(dict(zip(("source_artifact_id", "artifact_sha256", "sku_id", "passport_id", "conflict_id",
                             "decision", "value", "decision_source", "decided_by"), p),
                        id=len(DEC) + 1, decided_at=pd.Timestamp("2026-10-28 10:00", tz="UTC")))

    def fetchone(self):
        return (len(DEC),)

    def close(self):
        pass


import services.db as db  # noqa: E402
db.get_conn = lambda: WConn()


class _Cur:
    def __init__(self):
        self.description, self._rows = [], []

    def execute(self, sql, params=None):
        if "sku_master" not in sql:
            raise RuntimeError("в тесте Кабинет отвечает только справочником")
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


class Store:
    def get(self, loc):
        assert loc == LOC, loc
        return DOCX


pc.volume_store = lambda: Store()
from services import product_specs as ps  # noqa: E402

ps.load = lambda asin, mp: ({"title": "Aspirador Soplador de Jardín Dnipro-M DVB-200BC Dual 20V, Triturador 15:1",
                             "attributes": {}, "amazon_type": "LEAF_BLOWER", "product_information": {},
                             "item_highlight": ""}, None) if (asin, mp) == ("B0GTRY26HB", "es") else (None, "нет")

import auth  # noqa: E402
import services.passport as pp  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

# ================================================================ сервис
print("(2), (4) Реестр и поиск — сервис")
st.cache_data.clear()
data = pp.load_registry()
directory, _ = pp.sku_directory()
check("Реестр прочитан без сбоя, копия стала паспортом SKU",
      data["error"] is None and list(data["objects"]["sku_id"]) == ["99601000-B"]
      and data["objects"].iloc[0]["source"] == "copy")
rows = pp.registry_rows(directory[directory["sku"] == "99601000-B"], data, {}, "y@dniprom.com", ())
r = rows.iloc[0]
check("(2) у 99601000-B паспорт есть: v2, «NOT_READY» из шапки, модель из копии",
      r["has_passport"] and r["state"] == "NOT_READY" and r["passport_version"] == "2" and r["model"] == "DVB-200BC Dual")
check("(2) SHA копии подтверждён — данные актуальны", r["fresh"] == pp.CURRENT)
check("(2) следующее действие — не «Создать Паспорт»", r["action"] != pp.CREATE)
for q in ("99601000-B", "dvb-200bc", "Пилосос садовий", "B0GTRY26HB", "4823102367354"):
    view, n = pp.search(directory, data["objects"], q)
    check(f"(4) поиск «{q}» находит 99601000-B", "99601000-B" in set(view["sku"]))
view, _ = pp.search(directory, data["objects"], "")
check("(4) без запроса — товары с паспортом, и копия среди них", list(view["sku"]) == ["99601000-B"])
MODE["objects"] = pd.DataFrame([dict(zip(OBJ_COLS, ("PSP-1", "L", "99601000-B", "1", None, "DVB-200BC", "READY", "3",
                                                     "c" * 64, None, None, "[]", "APPLIED", TS, "c" * 64, TS)))])
st.cache_data.clear()
d2 = pp.load_registry()
check("есть строка passport_objects — главнее она, второй строки на SKU нет",
      len(d2["objects"]) == 1 and d2["objects"].iloc[0]["source"] == "engine" and d2["objects"].iloc[0]["state"] == "READY")
MODE["objects"] = pd.DataFrame(columns=OBJ_COLS)


class BadStore:
    def get(self, loc):
        raise OSError("том недоступен")


pc.volume_store = lambda: BadStore()
st.cache_data.clear()
d3 = pp.load_registry()
check("том не читается — паспорт есть, но с причиной и без подтверждённой свежести",
      d3["objects"].iloc[0]["copy_error"].startswith("OSError") and d3["objects"].iloc[0]["readback_sha256"] is None)
pc.volume_store = lambda: Store()
pp.load_registry.clear()             # кэш Реестра — 60 с; кэш копии НЕ чистим: сбой не должен в нём остаться
d4 = pp.load_registry()
check("том починили — копия читается сразу, сбой не закэширован на сутки (проверка #176)",
      not d4["objects"].iloc[0]["copy_error"] and d4["objects"].iloc[0]["model"] == "DVB-200BC Dual")
pc.volume_store = lambda: None
check("нет доступа к тому — код причины, а не текст мимо перевода",
      pp.copy_summary(LOC, "e" * 64)["error"] == pp.COPY_NO_STORE)
pc.volume_store = lambda: Store()
check("SHA в томе другой — код причины", pp.copy_summary(LOC, "f" * 64)["error"] == pp.COPY_SHA_MISMATCH)
check("в Реестр идёт только действующая копия: прежняя (OLD) — нет",
      list(d4["objects"]["source_artifact_id"]) == [AID])


# ================================================================ экран
def page(**state):
    st.cache_data.clear()
    st.cache_resource.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.switch_page("pages/content.py")
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def texts(at) -> str:
    out = []
    for coll in (at.markdown, at.caption, at.info, at.warning, at.error, at.success):
        out += [str(x.value) for x in coll]
    return "\n".join(out)


def frames(at) -> list[pd.DataFrame]:
    return [d.value for d in at.dataframe if isinstance(d.value, pd.DataFrame)]


from i18n import t  # noqa: E402

print("(1), (3) Создание")
at = page(**{"pp-tab": "create", "pp-sku": "99601000-B"})
check("вкладка «Создание» открывается без ошибки", not at.exception)
T = texts(at)
check("(2) сказано, что паспорт есть — копия v2, та же, что у генератора", AID in T and "v2" not in "" and
      t("pp.create_copy", aid=AID, ver="2", state=t("pp.state.NOT_READY")) in T)
check("(2) «Создать Паспорт» не предлагается", not any(b.key == "pp-create-off" for b in at.button))
check("(3) блок загрузки docx — тот же, что в генераторе (подсказка про том UC)",
      t("tg.pp.hint", volume=pc.VOLUME) in T and t("pp.up.title") in T)
summary = next((f for f in frames(at) if "field" in f.columns and t("pp.sum.asin_es") in set(f["field"])), None)
check("(1) «Собрано по SKU»: название, EAN, ASIN и ASIN ES из справочника и матрицы",
      summary is not None and {"Пилосос садовий DVB-200BC Dual + 2 АКБ", "4823102367354", "B0GTRY26HB"}
      <= set(summary["value"]) and dict(zip(summary["field"], summary["value"]))[t("pp.sum.asin_es")] == "B0GTRY26HB")
check("(1) тип и модель — из листинга, текущий тайтл назван",
      any(str(m.value) == t("tg.type.blower") for m in at.metric)
      and t("pp.sum.title_now", asin="B0GTRY26HB",
            title="Aspirador Soplador de Jardín Dnipro-M DVB-200BC Dual 20V, Triturador 15:1") in T)
check("(1) ручного ввода фактов нет: на «Создании» только комментарий-контекст",
      [w.key for w in at.text_input] == [] and [w.key for w in at.text_area] == ["pp-comment-99601000-B"])
MODE["matrix_fail"] = True
at = page(**{"pp-tab": "create", "pp-sku": "99601000-B"})
check("(1) матрица не прочиталась — сказано «не прочитано», а не «у SKU нет ASIN на ES»",
      t("tg.link.src_matrix", err="RuntimeError: матрица недоступна")[:20] in texts(at)
      and t("pp.sum.no_es") not in texts(at))
MODE["matrix_fail"] = False
MODE["objects"] = pd.DataFrame([dict(zip(OBJ_COLS, ("PSP-1", "L", "99601000-B", "1", None, "DVB-200BC", "READY", "3",
                                                     "c" * 64, None, None, "[]", "APPLIED", TS, "c" * 64, TS)))])
at = page(**{"pp-tab": "create", "pp-sku": "99601000-B"})
check("паспорт ведёт движок — загрузки docx на «Создании» нет, сказано почему (второй паспорт)",
      t("pp.up.engine") in texts(at) and t("tg.pp.hint", volume=pc.VOLUME) not in texts(at))
MODE["objects"] = pd.DataFrame(columns=OBJ_COLS)

print("(6) карточка паспорта")
at = page(**{"pp-tab": "registry", "pp-sku": "99601000-B", "pp-q": "99601000-B", "pp-show": "passport"})
check("Реестр с карточкой паспорта открывается", not at.exception)
kit = next((f for f in frames(at) if "qty" in f.columns), None)
check("(6) комплектация с количествами: колёса 1, АКБ BP-240 — 2",
      kit is not None and dict(zip(kit["item"], kit["qty"])) == {"Колеса": "1", "Акумулятор BP-240 4 Ah": "2"})
conf = next((f for f in frames(at) if {"a", "b", "state", "src"} <= set(f.columns)), None)
check("(6) конфликты со статусом в паспорте и состоянием: 002 открыт, 005 закрыт в паспорте",
      conf is not None and dict(zip(conf["id"], conf["state"])) == {
          "CONFLICT-99601000-B-002": t("pp.cf.open"), "CONFLICT-99601000-B-005": t("pp.cf.closed"),
          "CONFLICT-99601000-B-007": t("pp.cf.open")}
      and dict(zip(conf["id"], conf["status"]))["CONFLICT-99601000-B-002"] == "OPEN_OWNER_DECISION")

pc.volume_store = lambda: BadStore()
at = page(**{"pp-tab": "registry", "pp-sku": "99601000-B", "pp-q": "99601000-B"})
check("том не читается — в карточке Реестра причина названа сразу, паспорт не выдан за отсутствующий",
      any("OSError: том недоступен" in str(e.value) for e in at.error) and t("pp.create_absent") not in texts(at))
pc.volume_store = lambda: Store()

print("(7) верификатор закрывает конфликт")
at = page(**{"pp-tab": "verifier", "pp-sku": "99601000-B"})
check("вкладка Верификатора открывается", not at.exception)
CID = "CONFLICT-99601000-B-002"
check("стороны конфликта на экране как текст: «$» и «*», «[…]» экранированы (проверка #176)",
      r"\$5 \[x\]" in texts(at) and r"\*ManoMano\*" in texts(at))
save = next((b for b in at.button if b.key == f"pp-cfd-save-0-{CID}-0"), None)
check("у открытого конфликта есть форма решения; без выбора стороны кнопка выключена", save is not None and save.disabled)
check("у закрытого в паспорте — формы нет, сказано, что закрыт",
      not any(b.key.startswith("pp-cfd-save-1-CONFLICT-99601000-B-005") for b in at.button)
      and t("pp.dec.closed_in_passport", src="—") in texts(at))
at.radio(key=f"pp-cfd-kind-0-{CID}-0").set_value("SIDE_B").run()
at.button(key=f"pp-cfd-save-0-{CID}-0").click().run()
check("без источника — отказ словами, строки нет", not DEC and t("pp.dec.err.NO_SOURCE") in texts(at))
at.text_input(key=f"pp-cfd-src-0-{CID}-0").set_value("чат 21.10, Ярослав").run()
_req = auth.require
auth.require = lambda *a, **k: False              # кнопка включена, а право в момент нажатия снято
at.button(key=f"pp-cfd-save-0-{CID}-0").click().run()
check("право проверяется в момент нажатия: снято между отрисовкой и нажатием — строки нет", not DEC)
auth.require = _req
at.button(key=f"pp-cfd-save-0-{CID}-0").click().run()
check(f"решение записано одной строкой: сторона B, источник, копия и SHA ({len(DEC)})",
      len(DEC) == 1 and DEC[0]["decision"] == "SIDE_B" and DEC[0]["decision_source"] == "чат 21.10, Ярослав"
      and (DEC[0]["source_artifact_id"], DEC[0]["artifact_sha256"], DEC[0]["sku_id"]) == (AID, SHA, "99601000-B"))
check("номер решения на экране, поля пересозданы с новым ключом (правило 7б)",
      t("pp.dec.saved", cid=CID, id=1) in texts(at) and any(b.key == f"pp-cfd-save-0-{CID}-1" for b in at.button)
      and not any(w.key.endswith("-0") and w.key.startswith("pp-cfd-") for w in at.text_input))
check("конфликт показан решённым, с источником",
      t("pp.dec.current", value="Marketplace: 2× BP-240 4 Ah + FC-230 Dual",
        src="чат 21.10, Ярослав · " + DEC[0]["decided_by"] + " · 28.10.2026 10:00") in texts(at))
at = page(**{"pp-tab": "registry", "pp-sku": "99601000-B", "pp-q": "99601000-B", "pp-show": "passport"})
conf = next((f for f in frames(at) if {"a", "b", "state", "src"} <= set(f.columns)), None)
check("(6) в карточке — решённым, с решённым значением и источником решения",
      conf is not None and dict(zip(conf["id"], conf["state"]))[CID] == t("pp.cf.decided")
      and dict(zip(conf["id"], conf["value"]))[CID] == "Marketplace: 2× BP-240 4 Ah + FC-230 Dual"
      and "чат 21.10, Ярослав" in dict(zip(conf["id"], conf["src"]))[CID])

_can, _req = auth.can, auth.require
auth.can = lambda a: a != "ls.textgen.accept" and _can(a)
at = page(**{"pp-tab": "verifier", "pp-sku": "99601000-B"})
g = int(at.session_state["pp-cfd-gen"]) if "pp-cfd-gen" in at.session_state else 0
at.radio(key=f"pp-cfd-kind-0-{CID}-{g}").set_value("SIDE_B").run()     # сторона выбрана: выключает право, а не выбор
check("без права ls.textgen.accept — кнопка выключена и при выбранной стороне, сказано, чьё это право",
      at.button(key=f"pp-cfd-save-0-{CID}-{g}").disabled and t("pp.dec.denied_hint") in texts(at))
auth.can = _can
MODE["no_decisions_table"] = True
at = page(**{"pp-tab": "verifier", "pp-sku": "99601000-B"})
g = int(at.session_state["pp-cfd-gen"]) if "pp-cfd-gen" in at.session_state else 0
at.radio(key=f"pp-cfd-kind-0-{CID}-{g}").set_value("SIDE_B").run()
check("без миграции решений — кнопка выключена и при выбранной стороне, файл назван",
      at.button(key=f"pp-cfd-save-0-{CID}-{g}").disabled
      and t("pp.dec.migration_missing", file="2026-10-28_passport_conflict_decisions.sql") in texts(at))
MODE["no_decisions_table"] = False

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
