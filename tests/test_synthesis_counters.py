# -*- coding: utf-8 -*-
"""
tests/test_synthesis_counters.py — числа в шапке Синтеза проверяемы.

Пока в шапке стояло одно общее число, разрез по стране проверить было
нечем: фильтр мог считать неверно, и это выглядело бы нормально. Теперь
рядом с отфильтрованным числом стоит общее — расхождение видно глазом.
Проверки стерегут ровно это свойство:

  · без фильтра «всего» не показывается — оба числа совпали бы и мешали;
  · с фильтром показаны оба, и отфильтрованное меньше общего;
  · фильтр читается из состояния виджета, хотя шапка рисуется ВЫШЕ него;
  · деньги, число тайтлов и SQP режутся тем же фильтром, а не только
    счётчик товаров.

Запуск (pytest не нужен):  python tests/test_synthesis_counters.py
"""
from __future__ import annotations

import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type(
    "C", (), {"close": lambda self: None})()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# три товара в Испании, два в Германии; SQP есть у двух испанских
CAND = pd.DataFrame([
    dict(asin=f"B0ES{i}", marketplace="es", sku_group=f"1750000{i}",
         title="Título muy largo de Dnipro-M " * 4,
         fetched_at=pd.Timestamp("2026-08-26"), main_image=None)
    for i in range(3)
] + [
    dict(asin=f"B0DE{i}", marketplace="de", sku_group=f"2250000{i}",
         title="Sehr langer Dnipro-M Titel " * 4,
         fetched_at=pd.Timestamp("2026-08-26"), main_image=None)
    for i in range(2)
])
SQP = pd.DataFrame([dict(asin="B0ES0", marketplace="es"),
                    dict(asin="B0ES1", marketplace="es")])
ECON = pd.DataFrame([
    dict(asin="B0ES0", marketplace="es", revenue_30d=1000.0, sessions_30d=10,
         conversion=0.1, buy_box_pct=100.0, shipping_template=""),
    dict(asin="B0DE0", marketplace="de", revenue_30d=500.0, sessions_30d=5,
         conversion=0.1, buy_box_pct=100.0, shipping_template=""),
])


def fake_sql(sql, conn, **kw):
    s = str(sql)
    if "FROM diagnosis d" in s and "title_over_limit" in s:
        return CAND.copy()
    if "FROM sqp_reports" in s and "DISTINCT asin" in s:
        return SQP.copy()
    if "FROM asin_economics" in s:
        return ECON.copy()
    if "FROM synthesis_skill" in s:
        return pd.DataFrame([dict(scope="title_split", skill_text="м",
                                  version=1)])
    return pd.DataFrame()


pd.read_sql = fake_sql
from streamlit.testing.v1 import AppTest              # noqa: E402


def header_of(at) -> str:
    """Шапка — первый markdown со словом «Под риском»."""
    for m in at.markdown:
        v = str(m.value)
        if "Под риском" in v or "At risk" in v or "Під ризиком" in v:
            return v
    return ""


# между числом и «всего» может стоять подпись метрики («3 тайтлов сверх
# лимита · всего 5») — поэтому между тегами допускаем текст, но не теги
PAIR_RE = r"<b[^>]*>([^<]+)</b>[^<]*<span[^>]*>\s*·\s*всего ([^<]+)</span>"


def numbers(html: str) -> list[str]:
    """Жирные числа шапки по порядку: деньги, тайтлы, SQP."""
    return re.findall(r"<b[^>]*>([^<]+)</b>", html)


# --- без фильтра
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/synthesis.py").run()
head = header_of(at)
check("шапка отрисована", bool(head))
check("общее число товаров в шапке", " 5 " in head or ">5<" in head)
check("без фильтра «всего» не показывается", "всего" not in head)

# --- фильтр по Испании
at.session_state["syn-mp"] = ["es"]
at.run()
head = header_of(at)
nums = numbers(head)
check("страна названа человеческим именем", "Испания" in head)
check("показаны оба числа: разрез и общее", "всего" in head)
check("три жирных числа: деньги, тайтлы, SQP", len(nums) >= 4)

pairs = re.findall(PAIR_RE,
                   head)
check("у каждого числа своя пара «разрез · всего»", len(pairs) == 3)
if len(pairs) == 3:
    money, titles, sqp = pairs
    check("тайтлов по Испании 3 из 5",
          titles[0].strip() == "3" and titles[1].strip() == "5")
    check("SQP по Испании 2 из 2", sqp[0].strip() == "2" and sqp[1].strip() == "2")
    check("деньги тоже разрезаны, а не общие",
          money[0].strip() != money[1].strip())

# --- фильтр по Германии: числа обязаны поменяться
at.session_state["syn-mp"] = ["de"]
at.run()
pairs_de = re.findall(
    PAIR_RE,
    header_of(at))
check("страна переключилась", "Германия" in header_of(at))
if len(pairs_de) == 3:
    check("тайтлов по Германии 2 из 5",
          pairs_de[1][0].strip() == "2" and pairs_de[1][1].strip() == "5")
    check("SQP по Германии 0 из 2",
          pairs_de[2][0].strip() == "0" and pairs_de[2][1].strip() == "2")
else:
    check("тайтлов по Германии 2 из 5", False)
    check("SQP по Германии 0 из 2", False)

# --- разрез не должен трогать общее
check("общее число не поехало от фильтра",
      all(p[1].strip() == q[1].strip()
          for p, q in zip(pairs, pairs_de)) if len(pairs_de) == 3 else False)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
