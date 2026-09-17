# -*- coding: utf-8 -*-
"""
tests/test_catalog_age.py — возраст данных в Каталоге виден, а не подразумевается.

Сбор снапшотов идёт по кругу: ежедневный прогон берёт около четверти
пар, и каждая карточка обновляется примерно раз в неделю (проверено
по базе 17.09: возраст пар раскладывается ровно на семь дневных
корзин, плюс хвост из 33 пар старше недели и 20 никогда не собранных).
Дата «16.09 10:00» на карточке через четыре дня читалась как «на
днях», и цифры четырёхдневной давности выглядели сегодняшними.

Проверяются три вещи:
  · у каждого рынка на экране — не дата прогона, а сколько пар
    старше недели и сколько не собирались: это и есть «данным можно
    верить или нет»;
  · у карточки рядом с датой стоит возраст словами, и «сегодня»
    появляется только у сегодняшней;
  · старше недели — выделено, чтобы не сливалось с остальными.

Запуск (pytest не нужен):  python tests/test_catalog_age.py
"""
from __future__ import annotations

import json
import pathlib
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


RAW = json.dumps({"images": ["a"], "number_of_videos": 1, "aplus": True,
                  "average_rating": "4,5", "price": "10", "sold_by": "Dnipro-M"})
NOW = pd.Timestamp.now("UTC")


def product(asin, mp, days):
    ts = pd.NaT if days is None else (NOW - pd.Timedelta(days=days, hours=1))
    return dict(sku_group=f"175{asin}", asin=asin, marketplace=mp,
                is_competitor=False, fetched_at=ts, ok=True if days is not None else None,
                title="T" if days is not None else None, in_stock=True,
                review_count=100, is_amazon_choice=False,
                raw=RAW if days is not None else None)


# ES: сегодня, четыре дня, десять дней, никогда. IT: всё свежее.
CAT = pd.DataFrame([
    product("B0TODAY", "es", 0),
    product("B0FOUR", "es", 4),
    product("B0TEN", "es", 10),
    product("B0NEVER", "es", None),
    product("B0IT1", "it", 1),
    product("B0IT2", "it", 2),
])


def fake_sql(sql, conn, **kw):
    s = str(sql)
    if "FROM product_matrix m" in s and "is_amazon_choice" in s:
        return CAT.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
from streamlit.testing.v1 import AppTest              # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/catalog.py").run()
check("страница отрисована без ошибки", not at.exception)

html = " ".join(str(m.value) for m in at.markdown)

# --- 1. полоса по рынкам
strip = next((str(m.value) for m in at.markdown
              if "<b style=" in str(m.value) and ">ES</b>" in str(m.value)), "")
check("полоса возраста по рынкам есть", bool(strip) and ">IT</b>" in strip)
check("ES: названо, сколько старше недели и сколько не собирались",
      "старше недели: 1" in strip and "не собирались: 1" in strip)
check("IT: без хвостов — ни «старше недели», ни «не собирались»",
      "IT</b>" in strip and strip.split(">IT</b>")[1].split("</span></span>")[0]
      .count("старше") == 0)
check("и сказано, что сбор идёт по кругу",
      any("по кругу" in str(c.value) for c in at.caption))


def card(asin: str) -> str:
    return next((str(m.value) for m in at.markdown if asin in str(m.value)
                 and "назад" in str(m.value) or asin in str(m.value)
                 and "сегодня" in str(m.value) or asin in str(m.value)
                 and "не собирался" in str(m.value)), "")


# --- 2. возраст словами на карточке
check("сегодняшняя — «сегодня»", "сегодня" in card("B0TODAY"))
check("четырёхдневная — «4 дня назад», а не «сегодня»",
      "4 дня назад" in card("B0FOUR") and "сегодня" not in card("B0FOUR"))
check("десятидневная — «10 дней назад»", "10 дней назад" in card("B0TEN"))
check("несобранная — «не собирался», без даты", "не собирался" in card("B0NEVER"))

# --- 3. старше недели выделено, свежее — нет
import pages  # noqa: E402,F401  (пакет страниц; константы читаем из файла)
src = (ROOT / "pages/catalog.py").read_text(encoding="utf-8")
warn = src.split('WARN_TEXT = "')[1].split('"')[0]
muted = src.split('MUTED = "')[1].split('"')[0]
c10, c4 = card("B0TEN"), card("B0FOUR")
check("старше недели — предупреждающим цветом",
      f'color:{warn};">10 дней назад' in c10)
check("четыре дня — приглушённым, не предупреждающим",
      f'color:{muted};">4 дня назад' in c4 and warn not in c4.split("4 дня назад")[0][-40:])

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
