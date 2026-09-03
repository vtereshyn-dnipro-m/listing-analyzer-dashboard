# -*- coding: utf-8 -*-
"""
tests/test_tables_photo_asin.py — фото и кликабельный ASIN во всех списках.

Три свойства, и каждое ломается тихо.

ДОМЕН. Ссылка на карточку девять раз собиралась строкой
`https://www.amazon.{marketplace}/dp/{asin}`. Работало по совпадению:
код рынка в этом проекте и есть доменный суффикс. Совпадение неполное —
у Бельгии код `be`, а витрина живёт на amazon.com.be, и ссылка вела
на несуществующий сайт. Заметить это можно было только кликнув, поэтому
здесь домены проверяются по фактам, а не по формуле.

ЗАГЛУШКА. `ImageColumn` при пустом значении рисует пустую ячейку:
«фото нет» выглядит как «столбец не про это», а строки разъезжаются по
высоте. Поэтому вместо пустоты — серый квадрат.

КЛЮЧИ. В Матрице по колонке `asin` строились ключи для сбора и удаления.
Подменив ASIN на ссылку и оставив прежний способ, мы получили бы кнопку
«Удалить выбранные», которая молча не удаляет ничего. Поэтому проверяется
не наличие ссылки, а то, что ВЫБОР строки по-прежнему указывает на тот же
товар.

Запуск (pytest не нужен):  python tests/test_tables_photo_asin.py
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


T = pd.Timestamp
IMG = "https://m.media-amazon.com/images/I/71abc.jpg"

# два товара: у первого фото есть, у второго нет; рынки es и be —
# be здесь не для полноты, а потому что именно он ломал ссылку
ROWS = pd.DataFrame([
    dict(asin="B0AAA", marketplace="es", sku_group="17557000",
         is_competitor=False, title="Martillo Percutor " * 5,
         fetched_at=T("2026-09-03"), ok=True, review_count=10,
         main_image=IMG, raw={}, rating=4.5, last_ok=True,
         last_fetch=T("2026-09-03"), red=1, amber=0, yellow=0,
         added_at=T("2026-08-01"), created_at=T("2026-09-03"),
         analysis_type="gallery", grade=None, images_analyzed=None,
         has_aplus=False, price=None, seller=None),
    dict(asin="B0BBB", marketplace="be", sku_group="17557001",
         is_competitor=False, title="Boormachine " * 5,
         fetched_at=T("2026-09-03"), ok=True, review_count=5,
         main_image=None, raw={}, rating=4.0, last_ok=True,
         last_fetch=T("2026-09-03"), red=1, amber=0, yellow=0,
         added_at=T("2026-08-01"), created_at=T("2026-09-03"),
         analysis_type="gallery", grade=None, images_analyzed=None,
         has_aplus=False, price=None, seller=None),
])
DIAG = pd.DataFrame([
    dict(asin=r["asin"], marketplace=r["marketplace"],
         sku_group=r["sku_group"], rule_id="title_over_limit", severity="red",
         pain="длинный тайтл", cause="c", action="a", money_impact=100.0,
         created_at=T("2026-09-03"), title=r["title"],
         fetched_at=T("2026-09-03"), main_image=r["main_image"])
    for _, r in ROWS.iterrows()])


def fake_sql(sql, conn=None, **kw):
    s = str(sql)
    if "FROM diagnosis" in s:
        return DIAG.copy()
    if ("FROM listing_snapshots" in s or "FROM product_matrix" in s
            or "listing_latest" in s):
        return ROWS.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql

import services.marketplaces as mk                      # noqa: E402
from streamlit.testing.v1 import AppTest                # noqa: E402

STUB = mk.PLACEHOLDER_IMG


def page(path: str, mode_key: str | None = None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    at.switch_page(path).run()
    if mode_key:
        at.session_state[mode_key] = "table"
        at.run()
    return at


def tables(at) -> list:
    return [d.value for d in at.dataframe] + \
           [d.value for d in getattr(at, "data_editor", [])]


def col(df, *names):
    for n in names:
        if n in df.columns:
            return list(df[n])
    return []


# --- домены: главная находка
check("Бельгия ведёт на amazon.com.be, а не на несуществующий amazon.be",
      mk.product_url("B0BBB", "be") == "https://www.amazon.com.be/dp/B0BBB")
check("Испания не пострадала",
      mk.product_url("B0AAA", "es") == "https://www.amazon.es/dp/B0AAA")

# --- три таблицы: Диагноз, Каталог, Фото
for _name, _path, _mode in (("Диагноз", "pages/dashboard.py", "diag_mode"),
                            ("Каталог", "pages/catalog.py", "cat_mode"),
                            ("Фото и A+", "pages/photo.py", "ph-mode")):
    at = page(_path, _mode)
    check(f"{_name}: таблица отрисована", not at.exception and tables(at))
    if at.exception or not tables(at):
        continue
    df = tables(at)[0]
    photos = col(df, "img", "main_image", "фото")
    asins = col(df, "asin", "ASIN")
    check(f"{_name}: в таблице есть колонка фото", bool(photos))
    check(f"{_name}: пустое фото заменено заглушкой, а не пустой ячейкой",
          all(str(v).startswith(("http", "data:")) for v in photos))
    check(f"{_name}: ASIN — ссылка на карточку",
          bool(asins) and all(str(a).startswith("https://www.amazon.")
                              for a in asins))
    check(f"{_name}: домен бельгийского товара верный",
          any("amazon.com.be/dp/B0BBB" in str(a) for a in asins))
    check(f"{_name}: колонки-дубля «открыть» больше нет",
          "link" not in df.columns and "ссылка" not in df.columns)

# --- Синтез: фото вернулось в строку ленты
at = page("pages/synthesis.py")
_rows = [str(m.value) for m in at.markdown
         if 'class="ls-card"' in str(m.value)]
check("Синтез: строки ленты отрисованы", bool(_rows))
check("Синтез: в каждой строке есть фото",
      all(re.search(r'<img src="(https://|data:)', r) for r in _rows))
check("Синтез: у товара без фото стоит заглушка",
      any(STUB[:40] in r for r in _rows))

# --- Матрица: ссылка не должна ломать выбор строк
SRC = (ROOT / "pages/matrix_setup.py").read_text(encoding="utf-8")
check("Матрица: ключи выбора берутся по индексу строки, а не из таблицы",
      'sel_idx = list(edited[edited["pick"]].index)' in SRC
      and 'sel_rows = chunk.loc[sel_idx]' in SRC)
check("Матрица: сбор идёт по тем же строкам", "collect_rows(sel_rows)" in SRC)
check("Матрица: удаление берёт пары из исходных строк, а не из колонки",
      'sel_keys = [(r["asin"], r["marketplace"]) for _, r in sel_rows.iterrows()]'
      in SRC)

# --- фото читается из снапшота с запасным путём
_sql_ok = sum("raw->'images'->>0" in (ROOT / p).read_text(encoding="utf-8")
              for p in ("pages/dashboard.py", "pages/matrix_setup.py",
                        "pages/synthesis.py"))
check(f"первый кадр галереи — запасной путь к фото ({_sql_ok} из 3)",
      _sql_ok == 3)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
