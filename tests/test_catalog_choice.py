# -*- coding: utf-8 -*-
"""
tests/test_catalog_choice.py — плашки Amazon's Choice в Каталоге.

Плашка простая, но три её случая ломаются тихо и по-разному:

  · товар ни разу не собирался — `is_amazon_choice` приходит NaN, а NaN
    в Python истинный. Через `bool()` карточка сказала бы «бейдж есть»
    там, где данных нет вообще (правило 4 проекта);
  · бейдж вернулся, а боль `lost_amazon_choice` ещё висит в diagnosis
    до следующего сбора. Красная «потерян» рядом с живым бейджем — это
    не неточность, а прямое враньё;
  · отсутствие бейджа плашкой не показывается вовсе: он есть у 19 ASIN,
    и «нет» на каждой второй карточке — шум, который прячет сигнал.

Запуск (pytest не нужен):  python tests/test_catalog_choice.py
"""
from __future__ import annotations

import json
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


RAW = json.dumps({"images": ["a"], "number_of_videos": 1, "aplus": True,
                  "average_rating": "4,5", "price": "10",
                  "sold_by": "Dnipro-M"})


def product(asin, choice):
    return dict(sku_group=f"175{asin}", asin=asin, marketplace="es",
                is_competitor=False, fetched_at=pd.Timestamp("2026-08-28"),
                ok=True, title="T", in_stock=True, review_count=100,
                is_amazon_choice=choice, raw=RAW)


CAT = pd.DataFrame([
    product("B0HAS", True),        # бейдж есть
    product("B0NONE", False),      # бейджа нет и не было
    product("B0LOST", False),      # бейдж потерян, боль на месте
    product("B0BACK", True),       # бейдж вернулся, боль ещё висит
    # ни разу не собирался: все поля снапшота NaN
    dict(sku_group="17500004", asin="B0NEW", marketplace="es",
         is_competitor=False, fetched_at=pd.NaT, ok=None, title=None,
         in_stock=None, review_count=None, is_amazon_choice=None, raw=None),
])
LOST = pd.DataFrame([
    dict(asin="B0LOST", marketplace="es",
         created_at=pd.Timestamp("2026-08-12")),
    dict(asin="B0BACK", marketplace="es",
         created_at=pd.Timestamp("2026-08-01")),
])


def fake_sql(sql, conn, **kw):
    s = str(sql)
    if "FROM product_matrix m" in s and "is_amazon_choice" in s:
        return CAT.copy()
    if "lost_amazon_choice" in s:
        return LOST.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
from streamlit.testing.v1 import AppTest              # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/catalog.py").run()
check("страница отрисована без ошибки", not at.exception)


def badge(asin: str) -> str:
    """Текст плашки Amazon's Choice на карточке товара, если она есть."""
    for m in at.markdown:
        v = str(m.value)
        if asin in v and "Amazon's Choice" in v:
            label = re.search(r"(Amazon's Choice[^<]*)</span>", v)
            value = re.search(
                r"Amazon's Choice[^<]*</span>\s*<b[^>]*>([^<]*)</b>", v)
            return f"{(label.group(1) if label else '').strip()}|" \
                   f"{value.group(1) if value else ''}"
    return ""


has = badge("B0HAS")
check("бейдж есть — плашка показана", has.startswith("Amazon's Choice|"))
check("и она не про потерю", "потерян" not in has)

check("бейджа нет и боли нет — плашки нет вовсе", badge("B0NONE") == "")
check("товар без сбора не получает плашку от NaN", badge("B0NEW") == "")

lost = badge("B0LOST")
check("потерянный бейдж назван потерянным", "потерян" in lost)
check("и с датой потери", "12.08.2026" in lost)

back = badge("B0BACK")
check("вернувшийся бейдж показан зелёной, а не «потерян»",
      back.startswith("Amazon's Choice|") and "потерян" not in back)

# цвет: зелёная и красная должны отличаться, иначе плашки неразличимы
def card(asin: str) -> str:
    return next((str(m.value) for m in at.markdown
                 if asin in str(m.value) and "Amazon's Choice" in str(m.value)),
                "")


green = re.search(r"background:(#\w+);color:(#\w+);[^']*'>\s*"
                  r"<span[^>]*>Amazon's Choice\s*</span>", card("B0HAS"))
red = re.search(r"background:(#\w+);color:(#\w+);[^']*'>\s*"
                r"<span[^>]*>Amazon's Choice потерян</span>", card("B0LOST"))
check("плашки различаются цветом",
      bool(green) and bool(red) and green.group(1) != red.group(1))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
