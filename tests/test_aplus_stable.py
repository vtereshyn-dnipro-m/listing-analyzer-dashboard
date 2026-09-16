# -*- coding: utf-8 -*-
"""
tests/test_aplus_stable.py — A+ читается стабилизированный, а не сырой.

ScrapingDog врёт про A+ примерно на 15% запросов, а на .it по отдельным
товарам на половине. Поэтому источник истины — `listing_latest.has_aplus`
(признак по трём последним снимкам), а не поле `aplus` последнего
снапшота.

Ошибка тут не выглядит ошибкой: карточка спокойно показывает «A+ нет»,
Диагноз заводит боль `no_aplus`, человек идёт делать A+, который уже есть.
Поэтому проверяется обе стороны — и что «нет» превращается в «есть», и
обратное: стабилизированный признак главнее сырого в любую сторону, иначе
это не стабилизация, а второе мнение.

Отдельно проверяется запасной путь: у товара первого сбора строки во вью
может не быть, и тогда читается сырое поле, а не «A+ нет».

Запуск (pytest не нужен):  python tests/test_aplus_stable.py
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


def raw(aplus: bool, modules: bool = False) -> str:
    d = {"images": ["a"] * 8, "number_of_videos": 1, "aplus": aplus,
         "average_rating": "4,6", "price": "10", "sold_by": "Dnipro-M"}
    if modules:
        d["aplus_images"] = ["m1", "m2"]
    return json.dumps(d)


def product(asin, raw_aplus, stable):
    return dict(sku_group=f"175{asin}", asin=asin, marketplace="it",
                is_competitor=False, fetched_at=pd.Timestamp("2026-08-29"),
                ok=True, title="Titolo", in_stock=True, review_count=100,
                is_amazon_choice=False, raw=raw(raw_aplus),
                has_aplus=stable)


# B0GLITCH — ровно тот случай, ради которого колонка появилась
CAT = pd.DataFrame([
    product("B0GLITCH", False, True),    # снапшот врёт «нет», на деле есть
    product("B0GONE", True, False),      # снапшот врёт «есть», на деле нет
    product("B0FIRST", True, None),      # во вью строки ещё нет
])


def fake_sql(sql, conn, **kw):
    s = str(sql)
    if "FROM product_matrix m" in s and "has_aplus" in s:
        return CAT.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
from streamlit.testing.v1 import AppTest              # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
at.switch_page("pages/catalog.py").run()
check("Каталог отрисован без ошибки", not at.exception)


def aplus_chip(asin: str) -> str:
    """Значение плашки A+ на карточке товара."""
    for m in at.markdown:
        v = str(m.value)
        if asin not in v:
            continue
        hit = re.search(r">A\+</span>\s*<b[^>]*>([^<]*)</b>", v)
        if hit:
            return hit.group(1).strip()
    return ""


check("вопреки снапшоту показано «есть» — стабилизированный главнее",
      aplus_chip("B0GLITCH") == "есть")
check("и обратно: снапшот говорит «есть», вью «нет» — верим вью",
      aplus_chip("B0GONE") == "нет")
check("без строки во вью читается сырое поле, а не «нет»",
      aplus_chip("B0FIRST") == "есть")

# --- здоровье считается по тому же признаку, иначе плашка и вердикт разойдутся
src = (ROOT / "pages/catalog.py").read_text(encoding="utf-8")
check("health() смотрит на ту же метрику, что и плашка",
      'if not mx["aplus"]' in src)
check("сырое поле больше не попадает в метрику напрямую",
      'bool(d.get("aplus"))' not in src.split("stable_aplus")[0])

# --- Диагноз: правило читает вью и делает это ПОСЛЕ записи снапшота
ms = (ROOT / "pages/matrix_setup.py").read_text(encoding="utf-8")
check("правило no_aplus берёт признак из listing_latest",
      "SELECT has_aplus FROM listing_latest" in ms)
check("чтение идёт после вставки снапшота — иначе вью не видит свежий",
      ms.index("INSERT INTO listing_snapshots")
      < ms.index("SELECT has_aplus FROM listing_latest"))
check("у правила остался запасной сырой признак",
      "else raw_aplus" in ms)

# --- Фото: «модулей нет» и «A+ нет» — разные сообщения
ph = (ROOT / "pages/photo.py").read_text(encoding="utf-8")
check("Фото тоже спрашивает вью, а не только сырое поле",
      "ll.has_aplus" in ph and 'r.get("has_aplus")' in ph)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
