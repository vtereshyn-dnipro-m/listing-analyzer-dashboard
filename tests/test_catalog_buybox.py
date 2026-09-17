# -*- coding: utf-8 -*-
"""
tests/test_catalog_buybox.py — Buy Box и BSR в Каталоге: колонка, иначе raw.

Сборщик с 18.09 пишет buy_box_owner/buy_box_seller и bsr_rank/
bsr_category колонками; у снапшотов до этого колонок нет. Экран обязан
показывать одно и то же для обоих: из колонки, когда она есть, и тем же
парсером из raw, когда нет. Две разные дороги к одному чипу — это
две возможности разойтись, поэтому проверяется РАВЕНСТВО результата.

Buy Box показывается всегда, когда снапшот есть: «нет предложения» —
состояние, объясняющее продажи, а не пустота. Правила Диагноза под
него пока нет намеренно (IE/co.uk не проверены глазами) — проверяется,
что боли из этого не растут.

Запуск (pytest не нужен):  python tests/test_catalog_buybox.py
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
services.db.get_conn = lambda: type("C", (), {"close": lambda self: None})()
from services.buybox import buy_box_of, OWN, AMAZON, OTHER, NONE   # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# --- 1. классификация Buy Box — на живых значениях
check("наш магазин по merchant id, имя любое",
      buy_box_of({"sold_by": "DNIPRO-M", "merchant_id": "A4JU8NB3VJG0K"}) == (OWN, "DNIPRO-M")
      and buy_box_of({"sold_by": "Dnipro-M-Store", "merchant_id": "A4JU8NB3VJG0K"})[0] == OWN)
check("Amazon EU — amazon", buy_box_of({"sold_by": "Amazon EU", "merchant_id": "A30DC7701CXIBH"}) == (AMAZON, "Amazon EU"))
check("чужой продавец — other с именем", buy_box_of({"sold_by": "ToolKing GmbH", "merchant_id": "AXXX"}) == (OTHER, "ToolKing GmbH"))
check("ни продавца, ни id — none", buy_box_of({"title": "x"}) == (NONE, None) and buy_box_of(None) == (NONE, None))
check("наш id и чужое имя — всё равно наш (id главнее)",
      buy_box_of({"sold_by": "Amazon", "merchant_id": "A4JU8NB3VJG0K"})[0] == OWN)

# --- 2. страница: колонка и raw дают один чип
NOW = pd.Timestamp.now("UTC")
ES_INFO = {"Rango de medicin": "40 Metros",
           "Clasificacin en los ms vendidos de Amazon":
           "nº1.830 en Jardín (Ver el Top 100 en Jardín) nº24 en Pulverizadores de jardinería"}


def raw(**kw):
    d = {"images": ["a"], "number_of_videos": 0, "aplus": False, "average_rating": "4,5",
         "price": "10", "product_information": ES_INFO}
    d.update(kw)
    return json.dumps(d)


def product(asin, sold_by=None, mid=None, cols=None):
    r = dict(sku_group=f"175{asin}", asin=asin, marketplace="es", is_competitor=False,
             status="active", collection_tier="weekly", weekly_day=3,
             fetched_at=NOW - pd.Timedelta(days=1), ok=True, title="T", in_stock=True,
             review_count=1, is_amazon_choice=False,
             raw=raw(**({"sold_by": sold_by, "merchant_id": mid} if mid or sold_by else {})),
             buy_box_owner=None, buy_box_seller=None, bsr_rank=None, bsr_category=None)
    if cols:
        r.update(cols)
    return r


CAT = pd.DataFrame([
    # старый снапшот: колонок нет, всё из raw
    product("B0OLDOWN", "DNIPRO-M", "A4JU8NB3VJG0K"),
    product("B0OLDNONE"),
    # новый снапшот: из колонок; raw НАРОЧНО противоречит — колонка главнее
    product("B0NEWAMZ", "DNIPRO-M", "A4JU8NB3VJG0K",
            cols=dict(buy_box_owner="amazon", buy_box_seller="Amazon EU",
                      bsr_rank=7, bsr_category="Taladros")),
    product("B0NEWOTH", cols=dict(buy_box_owner="other", buy_box_seller="ToolKing GmbH")),
])


def fake_sql(sql, conn=None, **kw):
    q = str(sql)
    if "FROM product_matrix m" in q and "is_amazon_choice" in q:
        return CAT.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
from streamlit.testing.v1 import AppTest              # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/catalog.py").run()
check("страница отрисована", not at.exception)


def card(asin):
    return next((str(m.value) for m in at.markdown if asin in str(m.value) and "Buy Box" in str(m.value)), "")


def chip_text(html, label):
    m = re.search(label + r"[^<]*</span>\s*<b[^>]*>([^<]*)</b>", html)
    return m.group(1).strip() if m else None


check("старый снапшот, наш магазин в raw — «наш»", chip_text(card("B0OLDOWN"), "Buy Box") == "наш")
check("старый снапшот без продавца — «нет предложения»",
      chip_text(card("B0OLDNONE"), "Buy Box") == "нет предложения")
check("новый снапшот — из колонки, не из raw (raw говорит «наш», колонка — Amazon)",
      chip_text(card("B0NEWAMZ"), "Buy Box") == "Amazon")
check("чужой — с именем продавца", (chip_text(card("B0NEWOTH"), "Buy Box") or "").startswith("чужой · ToolKing"))

# BSR: старый — парсером из raw (ES с ловушкой «Rango de medición»), новый — из колонки
check("старый снапшот: BSR разобран из raw мимо ловушки ключа",
      "#24 · Pulverizadores" in card("B0OLDOWN"))
check("новый снапшот: BSR из колонки", "#7 · Taladros" in card("B0NEWAMZ"))

# --- 3. правила Диагноза из Buy Box не растут — намеренно
src = (ROOT / "pages/catalog.py").read_text(encoding="utf-8")
check("правила buy_box_lost нет, пока IE/co.uk не проверены",
      "buy_box_lost" not in src and "buy_box_lost" not in
      (ROOT / "services/buybox.py").read_text(encoding="utf-8").split('"""', 2)[2])

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
