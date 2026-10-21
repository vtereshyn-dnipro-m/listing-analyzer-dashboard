# -*- coding: utf-8 -*-
"""
tests/test_product_specs.py — характеристики товара для тайтла (пилот, шаг 2).

Что ломается тихо и потому заперто:

1. **Тип инструмента.** productType у дрели и перфоратора один (DRILL), у пил —
   SAW. Ошибка типа даёт тайтл с чужими характеристиками, и он выглядит
   правдоподобно. Тип — по тайтлу, `drill_type=hammer_drill` — перфоратор.
2. **Источник у каждого значения, расхождение — вслух.** У DHR-202BC в атрибуте
   аккумулятор 4 Ah, в наборе и тайтле 6Ah: это `conflicts`, а не молча
   выбранное число.
3. **Что идёт в тайтл.** Порядок по таблице типов; мощность только у сетевого;
   вольтаж у инструмента — никогда; формат «2400W, Ø230mm, 6500rpm» проходит
   `services/title_rules.py` без нарушений формата единиц.
4. **Чего нет — названо** (`missing`): у перфоратора в данных нет энергии
   удара, и экран обязан это сказать, а не собрать тайтл без неё.
5. **«Не прочиталось» ≠ «нет характеристик»** у загрузчиков; ключи по типу —
   через `services/seo.py`, чужие бренды уходят в forbid.

Данные пяти пилотных товаров — `tests/fixture_pilot.py`, в форме базы.

Запуск (pytest не нужен):  python tests/test_product_specs.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import pandas as pd  # noqa: E402

from fixture_pilot import PILOT, texts, u, v  # noqa: E402
from services import product_specs as ps  # noqa: E402
from services import title_rules as tr  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


R = {a: ps.extract(a, "es", **d) for a, d in PILOT.items()}
DGA, GL, DHR, DSC, CD = (R[a] for a in ("B0H75P364R", "B0FZFCQN3H", "B0H75XRDBK", "B0GTRRBZNK", "B0DK5VZYVD"))

# ============================================================== 1. тип
print("1. тип инструмента")
check(f"пять пилотных: типы ({[r.tool_type for r in R.values()]})",
      [r.tool_type for r in (DGA, GL, DHR, DSC, CD)] == ["grinder", "grinder", "hammer", "circular_saw", "drill"])
check("перфоратор по тайтлу, хотя productType DRILL", DHR.tool_type == "hammer")
check("drill_type=hammer_drill делает перфоратором и «Taladro percutor»",
      ps.detect_type("Taladro Dnipro-M 20V", "DRILL", {"drill_type": v("hammer_drill")}) == "hammer")
check("перфоратор раньше дрели и без drill_type: «Martillo Perforador RH-100Q» (DRILL)",
      ps.detect_type("Martillo Perforador Dnipro-M RH-100Q SDS-Plus 880W", "DRILL", {}) == "hammer")
check("без тайтла — по productType", ps.detect_type("", "DISC_GRINDER_TOOL") == "grinder")
check("торцовочная раньше циркулярной", ps.detect_type("Sierra Ingletadora Dnipro-M 254mm", "SAW") == "miter_saw")
check("непонятное — None, а не первый попавшийся тип", ps.detect_type("Mochila de herramientas", "BAG") is None)
check("аккумулятор и зарядка — POWER_PACK",
      ps.extract("X", "es", title="Batería BP-260 20V 6Ah", amazon_type="BATTERY").kind == tr.POWER_PACK
      and ps.extract("X", "es", title="Cargador rápido FC-230", amazon_type="BATTERY_CHARGER").kind == tr.POWER_PACK)

# ============================================== 2. значения и источники
print("2. значения, источники, расхождения")
val = lambda r, f: (r.values[f].value, r.values[f].source) if f in r.values else None  # noqa: E731
check(f"DGA-201M: Ø125 и 10000rpm из атрибутов ({val(DGA, 'disc_mm')}, {val(DGA, 'rpm')})",
      val(DGA, "disc_mm") == (125.0, "attribute") and val(DGA, "rpm") == (10000.0, "attribute"))
check("GL-240: 2400W, Ø230, 6500rpm из атрибутов",
      val(GL, "power_w") == (2400.0, "attribute") and val(GL, "disc_mm") == (230.0, "attribute")
      and val(GL, "rpm") == (6500.0, "attribute"))
check(f"DSC-201BC: Ø165 и пропил 55mm из текста карточки ({val(DSC, 'disc_mm')}, {val(DSC, 'cut_depth_mm')})",
      val(DSC, "disc_mm") == (165.0, "snapshot") and val(DSC, "cut_depth_mm") == (55.0, "snapshot"))
check("CD-200BC: 60Nm и 1700rpm", val(CD, "torque_nm") == (60.0, "attribute") and val(CD, "rpm") == (1700.0, "attribute"))
check(f"DHR-202BC: аккумулятор 4 Ah в атрибуте против 6 Ah — расхождение названо один раз ({DHR.conflicts})",
      len(DHR.conflicts) == 1 and DHR.conflicts[0][0] == "capacity_ah"
      and DHR.conflicts[0][1].value == 4.0 and DHR.conflicts[0][2].value == 6.0)
check("у остальных расхождений нет", not any(r.conflicts for r in (DGA, GL, DSC, CD)))
check(f"модель: из атрибута, а у GL-240 — из тайтла ({[r.model for r in (DGA, GL, DHR)]})",
      DGA.model == "DGA-201M" and GL.model == "GL-240" and DHR.model == "DHR-202BC ULTRA")
check(f"сетевой / аккумуляторный ({[r.corded for r in (DGA, GL, DHR, DSC, CD)]})",
      [r.corded for r in (DGA, GL, DHR, DSC, CD)] == [False, True, False, False, False])

# ===================================================== 3. набор
print("3. набор")
check(f"DGA-201M: аккумулятор и зарядка, без самого инструмента и инструкции ({DGA.kit})",
      DGA.kit == ["Bateria BP-260 de 6Ah", "Cargador FC-230"])
check("DSC-201BC: в наборе только инструкция — набора нет", DSC.kit == [])
check("DHR-202BC: аккумулятор и зарядка", DHR.kit == ["Batería recargable BP-260 6A/h", "Cargador FC-230"])

# ===================================================== 4. в тайтл
print("4. характеристики в тайтл")
parts = {a: ps.title_parts(r) for a, r in R.items()}
check(f"DGA-201M: «Ø125mm, 10000rpm» — без мощности, аккумуляторная ({parts['B0H75P364R']})",
      parts["B0H75P364R"] == ["Ø125mm", "10000rpm"])
check(f"GL-240: «2400W, Ø230mm, 6500rpm» ({parts['B0FZFCQN3H']})", parts["B0FZFCQN3H"] == ["2400W", "Ø230mm", "6500rpm"])
check(f"DSC-201BC: «Ø165mm, 55mm» ({parts['B0GTRRBZNK']})", parts["B0GTRRBZNK"] == ["Ø165mm", "55mm"])
check(f"CD-200BC: «60Nm, 1700rpm» — мощность 432W не идёт, аккумуляторная ({parts['B0DK5VZYVD']})",
      parts["B0DK5VZYVD"] == ["60Nm", "1700rpm"])
check("вольтаж инструмента в тайтл не идёт никогда",
      not any(p.endswith("V") for p in sum(parts.values(), [])) and "voltage_v" in CD.values)
check("ни у одного вида инструмента вольтаж не стоит в полях тайтла (только у POWER_PACK)",
      all("voltage_v" not in t.fields for t in ps.TOOL_TYPES if t.kind == tr.TOOL))
cordless = ps.extract("X", "es", title="Amoladora Angular a Batería Dnipro-M 125mm", amazon_type="DISC_GRINDER_TOOL",
                      attributes={"maximum_power": u(800.0, "watts"), "power_source_type": texts("Baterías"),
                                  "wheel": [{"diameter": [{"unit": "millimeters", "decimal_value": 125.0}]}]})
check(f"аккумуляторная болгарка с мощностью в атрибутах — мощность в тайтл не идёт ({ps.title_parts(cordless)})",
      "power_w" in cordless.values and ps.title_parts(cordless) == ["Ø125mm"])
batt = ps.extract("X", "es", title="Batería Dnipro-M BP-260 20V 6Ah", amazon_type="BATTERY",
                  attributes={"voltage": u(20.0, "volts"),
                              "battery": [{"capacity": [{"unit": "amp_hours", "value": 6.0}]}]})
check(f"у аккумулятора вольтаж — главная характеристика ({ps.title_parts(batt)})", ps.title_parts(batt) == ["20V", "6Ah"])
for a, p in parts.items():
    t = "DNIPRO-M Herramienta " + " ".join(p)
    bad = [c for c in tr.codes(tr.check(t)) if c.startswith(("UNIT", "DIAMETER"))]
    check(f"{a}: формат характеристик проходит правила тайтла ({bad})", not bad)
check("формат: дробь с запятой, Ø, тысячи слитно",
      ps.fmt("impact_j", 2.8) == "2,8J" and ps.fmt("disc_mm", 230.0) == "Ø230mm" and ps.fmt("rpm", 10000.0) == "10000rpm")

# ===================================================== 5. чего нет
print("5. недостающее названо")
check(f"DHR-202BC: нет энергии удара, SDS и Ø бурения — названо ({DHR.missing})",
      DHR.missing == ["impact_j", "sds", "drill_concrete_mm"])
check(f"CD-200BC: нет патрона ({CD.missing})", CD.missing == ["chuck_mm"])
check("у аккумуляторного инструмента мощность недостающей не считается",
      "power_w" not in DGA.missing and "power_w" not in DSC.missing)
check("у пилотных болгарок всё на месте", DGA.missing == [] and GL.missing == [])

# ================================================= 6. текст карточки
print("6. разбор текста карточки")
tx = ps.from_text("Velocidad máxima de 10.000 rpm, 2,8J, Ø 125 mm, corte de 55 mm, SDS-Plus, 1.200W")
check(f"«10.000 rpm» — 10000, «2,8J» — 2.8 ({tx})", tx.get("rpm") == 10000 and tx.get("impact_j") == 2.8)
check("Ø с пробелом, пропил, SDS-Plus, 1.200W",
      tx.get("disc_mm") == 125 and tx.get("cut_depth_mm") == 55 and tx.get("sds") == "SDS-Plus")
check("«Modelo DHR-202BC» не даёт ни J, ни W", ps.from_text("Modelo DHR-202BC M14") == {})

# =========================================================== 7. чтение
print("7. загрузчики на подменённой базе")
import services.db as db  # noqa: E402

db.get_engine = lambda: object()
_real_read = pd.read_sql
QUERIES = []


def fake_read(sql, con=None, params=None, **kw):
    QUERIES.append((" ".join(sql.split())[:60], params))
    s = " ".join(sql.split())
    if "FROM listing_snapshots" in s:
        d = PILOT["B0H75XRDBK"]
        return pd.DataFrame([{"title": d["title"], "raw": {"product_information": d["product_information"],
                                                          "item_highlight": d["item_highlight"]}}])
    if "FROM listing_attributes" in s:
        return pd.DataFrame([{"product_type": "DRILL", "raw": {"attributes": PILOT["B0H75XRDBK"]["attributes"]}}])
    if "FROM product_matrix" in s:
        rows = [{"asin": a, "title": d["title"], "product_type": d["amazon_type"], "attributes": d["attributes"]}
                for a, d in PILOT.items()]
        rows.append({"asin": "B0OTHERDRL", "title": "Taladro Atornillador Dnipro-M CD-12QX 12V 25Nm",
                     "product_type": "DRILL", "attributes": float("nan")})
        return pd.DataFrame(rows)
    if "FROM sqp_reports" in s:
        return pd.DataFrame([
            {"search_query": "milwaukee", "volume": 13983, "impressions": 50, "clicks": 1, "purchases": 0, "asins": 3},
            {"search_query": "taladro percutor", "volume": 3000, "impressions": 400, "clicks": 9, "purchases": 1, "asins": 4},
            {"search_query": "martillo perforador", "volume": 2500, "impressions": 300, "clicks": 4, "purchases": 0, "asins": 2},
        ])
    raise AssertionError(s)


pd.read_sql = fake_read
try:
    got, err = ps.for_product("B0H75XRDBK", "es")
    check("for_product читает и разбирает", err is None and got.tool_type == "hammer" and got.conflicts)
    drills, err = ps.same_type_asins("drill", "es")
    check(f"same_type_asins: дрели — без перфоратора, NaN в атрибутах не роняет ({drills})",
          err is None and drills == ["B0DK5VZYVD", "B0OTHERDRL"])
    hammers, _ = ps.same_type_asins("hammer", "es")
    check(f"перфораторы отдельно ({hammers})", hammers == ["B0H75XRDBK"])

    from services import seo  # noqa: E402

    kw = seo.build_type_keyword_table(drills, "es", DHR.values and PILOT["B0DK5VZYVD"]["title"])
    tiers = dict(zip(kw["search_query"], kw["tier"]))
    check(f"ключи по типу: чужой бренд — forbid, с покупкой — must_keep ({tiers})",
          tiers.get("milwaukee") == "forbid" and tiers.get("taladro percutor") == "must_keep")
    check("в таблице видно, у скольких наших ASIN был запрос", "asins" in kw.columns)
    sq = [q for q in QUERIES if q[0].startswith("SELECT search_query")]
    check("запрос по всем ASIN типа одним обращением", sq and sq[-1][1]["asins"] == drills)
    n = len(QUERIES)
    check("пустой список ASIN — пусто без запроса к базе",
          seo.build_type_keyword_table([], "es", "x").empty and len(QUERIES) == n)

    def broken(*a, **k):
        raise RuntimeError("connection refused")

    pd.read_sql = broken
    got, err = ps.for_product("B0H75XRDBK", "es")
    check(f"сбой чтения — причина, а не пустые характеристики ({err})", got is None and "connection refused" in (err or ""))
    lst, err = ps.same_type_asins("drill", "es")
    check("сбой списка того же типа — причина", lst is None and err)
    kw = seo.build_type_keyword_table(["X"], "es", "x")
    check("сбой SQP — пусто и причина в sqp_error()", kw.empty and seo.sqp_error())
finally:
    pd.read_sql = _real_read

# ============================================================ 8. чистота
print("8. разбор чистый")
src = (ROOT / "services" / "product_specs.py").read_text(encoding="utf-8")
top = src.split("\ndef ", 1)[0]
check("модуль не тянет Streamlit и базу при импорте",
      "import streamlit" not in src and not re.search(r"^(from services\.db|import pandas)", top, re.M))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
